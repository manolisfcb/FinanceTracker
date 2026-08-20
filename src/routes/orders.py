import uuid
from datetime import datetime
from io import TextIOWrapper

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, or_

from src.extensions import db
from src.forms.ManualOrderForm import ManualOrderForm
from src.forms.OrdersImportForm import OrdersImportForm
from src.models import Account, Asset, OrderModel, OrderType
from src.resources.jobs.refresh_quotes import refresh_asset_quote
from src.resources.orders_import.registry import (
    get_importer,
    resolve_asset_id,
    resolve_or_create_manual_asset,
)
from src.routes.portfolio import portfolio_bp
from src.services.fx import fx_rate_to_cad_on


def _account_choices():
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name.asc()).all()
    return [(str(a.id), f"{a.name} ({a.type.value})") for a in accounts]


def _manual_order_values(form):
    """Validate and normalize the shared add/edit order form."""
    try:
        executed_at = datetime.strptime(form.executed_at.data, '%Y-%m-%d')
        quantity = float(form.quantity.data)
        price = float(form.price.data)
        fees = float(form.fees.data) if form.fees.data else 0.0
    except ValueError:
        flash('Cantidad, precio, comisiones o fecha inválidos', 'error')
        return None

    if quantity <= 0 or price < 0 or fees < 0:
        flash('La cantidad debe ser positiva; precio y comisiones no pueden ser negativos', 'error')
        return None

    try:
        account_id = int(form.account.data)
    except (TypeError, ValueError):
        account_id = None
    account = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
    if account is None:
        flash('La cuenta seleccionada no es válida', 'error')
        return None

    asset_id = None
    if form.asset_id.data:
        try:
            selected_asset = db.session.get(Asset, int(form.asset_id.data))
        except (TypeError, ValueError):
            selected_asset = None

        normalized_symbol = form.asset_symbol.data.strip().upper()
        if (
            selected_asset is not None
            and selected_asset.is_active
            and normalized_symbol in {
                selected_asset.symbol.upper(),
                selected_asset.yahoo_symbol.upper(),
            }
        ):
            asset_id = selected_asset.id

    if asset_id is None:
        asset_id = resolve_or_create_manual_asset(
            form.asset_symbol.data, currency_hint=form.currency.data,
        )
    if asset_id is None:
        flash(f'No se encontró el activo "{form.asset_symbol.data}" en el universo', 'error')
        return None

    currency = form.currency.data.strip().upper()
    fx_rate = fx_rate_to_cad_on(currency, executed_at.date())
    if fx_rate is None:
        flash(
            f'No hay tasa de cambio {currency}->CAD disponible. '
            'Los cambios no se guardaron para evitar un valor incorrecto en el portafolio.',
            'error',
        )
        return None

    return {
        'account_id': account.id,
        'asset_id': asset_id,
        'type': OrderType(form.type.data),
        'quantity': quantity,
        'price': price,
        'fees': fees,
        'currency': currency,
        'fx_rate_to_cad': fx_rate,
        'executed_at': executed_at,
        'broker': (form.broker.data or '').strip() or None,
    }


def _populate_manual_order_form(form, order):
    form.account.data = str(order.account_id)
    form.broker.data = order.broker or ''
    form.asset_symbol.data = order.asset.symbol
    form.asset_id.data = str(order.asset_id)
    form.type.data = order.type.value
    form.quantity.data = str(order.quantity)
    form.price.data = str(order.price)
    form.fees.data = str(order.fees)
    form.currency.data = order.currency
    form.executed_at.data = order.executed_at.strftime('%Y-%m-%d')


def _refresh_order_asset_quote(asset_id):
    """Best-effort quote refresh shared by order creation and editing."""
    if not current_app.config.get('REFRESH_QUOTE_ON_ORDER_CREATE', True):
        return
    asset = db.session.get(Asset, asset_id)
    try:
        if asset is not None and refresh_asset_quote(asset):
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning('Initial quote failed for asset %s: %s', asset_id, exc)


@portfolio_bp.route('/orders', methods=['GET'])
@login_required
def list_orders():
    account_id = request.args.get('account_id', type=int)
    query = OrderModel.query.filter_by(user_id=current_user.id)
    if account_id:
        query = query.filter_by(account_id=account_id)
    orders = query.order_by(OrderModel.executed_at.desc()).all()
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name.asc()).all()
    return render_template('orders.html', orders=orders, accounts=accounts, selected_account_id=account_id)


@portfolio_bp.route('/orders/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_order(id):
    order = OrderModel.query.filter_by(id=id, user_id=current_user.id).first()
    if not order:
        return {'message': 'Order not found'}, 404
    db.session.delete(order)
    db.session.commit()
    flash('Orden eliminada', 'success')
    return '', 204


@portfolio_bp.route('/orders/assets/search', methods=['GET'])
@login_required
def search_order_assets():
    """Return a small, ranked result set for the order asset combobox."""
    search_term = request.args.get('q', '').strip()[:50]
    if not search_term:
        return {'assets': []}

    prefix = f'{search_term}%'
    contains = f'%{search_term}%'
    assets = (
        Asset.query
        .filter(
            Asset.is_active.is_(True),
            or_(
                Asset.symbol.ilike(contains),
                Asset.yahoo_symbol.ilike(contains),
                Asset.name.ilike(contains),
            ),
        )
        .order_by(
            case(
                (Asset.symbol.ilike(prefix), 0),
                (Asset.yahoo_symbol.ilike(prefix), 1),
                (Asset.name.ilike(prefix), 2),
                else_=3,
            ),
            Asset.symbol.asc(),
            Asset.exchange.asc(),
        )
        .limit(8)
        .all()
    )
    return {
        'assets': [
            {
                'id': asset.id,
                'symbol': asset.symbol,
                'name': asset.name,
                'exchange': asset.exchange,
                'currency': asset.currency,
            }
            for asset in assets
        ]
    }


@portfolio_bp.route('/orders/add', methods=['GET', 'POST'])
@login_required
def add_order():
    form = ManualOrderForm()
    form.account.choices = _account_choices()

    if form.validate_on_submit():
        values = _manual_order_values(form)
        if values is None:
            return render_template('add_order.html', form=form, editing=False)

        order = OrderModel(user_id=current_user.id, **values)
        db.session.add(order)
        db.session.commit()
        _refresh_order_asset_quote(order.asset_id)
        flash('Orden agregada correctamente', 'success')
        return redirect(url_for('portfolio.list_orders'))

    return render_template('add_order.html', form=form, editing=False)


@portfolio_bp.route('/orders/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_order(id):
    order = OrderModel.query.filter_by(id=id, user_id=current_user.id).first()
    if order is None:
        abort(404)

    form = ManualOrderForm()
    form.account.choices = _account_choices()

    if form.validate_on_submit():
        values = _manual_order_values(form)
        if values is None:
            return render_template('add_order.html', form=form, editing=True)

        for field, value in values.items():
            setattr(order, field, value)
        db.session.commit()
        _refresh_order_asset_quote(order.asset_id)
        flash('Orden actualizada correctamente', 'success')
        return redirect(url_for('portfolio.list_orders'))

    if request.method == 'GET':
        _populate_manual_order_form(form, order)
    return render_template('add_order.html', form=form, editing=True)


@portfolio_bp.route('/orders/import', methods=['GET', 'POST'])
@login_required
def import_orders():
    form = OrdersImportForm()
    form.account.choices = _account_choices()

    if form.validate_on_submit():
        importer = get_importer(form.broker.data)
        csv_file = TextIOWrapper(form.file.data.stream, encoding='utf-8')
        try:
            parsed_rows = importer.parse(csv_file)
        except ValueError as exc:
            flash(f'Error procesando el archivo: {exc}', 'error')
            return render_template('orders_import.html', form=form)

        existing_hashes = {
            h for (h,) in OrderModel.query.with_entities(OrderModel.import_hash)
            .filter(OrderModel.import_hash.isnot(None))
            .all()
        }

        preview_rows = []
        for row in parsed_rows:
            import_hash = row.import_hash()
            asset_id = resolve_asset_id(row.symbol)
            preview_rows.append(
                {
                    "symbol": row.symbol,
                    "type": row.type,
                    "quantity": row.quantity,
                    "price": row.price,
                    "fees": row.fees,
                    "currency": row.currency,
                    "executed_at": row.executed_at.isoformat(),
                    "broker": row.broker,
                    "asset_id": asset_id,
                    "import_hash": import_hash,
                    "is_duplicate": import_hash in existing_hashes,
                    "is_unknown_symbol": asset_id is None,
                }
            )

        batch_id = uuid.uuid4().hex
        session[f"import_batch:{batch_id}"] = {
            "account_id": form.account.data,
            "rows": preview_rows,
        }

        return render_template(
            'orders_import_preview.html', batch_id=batch_id, rows=preview_rows
        )

    return render_template('orders_import.html', form=form)


@portfolio_bp.route('/orders/import/confirm', methods=['POST'])
@login_required
def confirm_import_orders():
    batch_id = request.form.get('batch_id')
    batch = session.get(f"import_batch:{batch_id}") if batch_id else None
    if not batch:
        flash('El lote de importación expiró, volvé a subir el archivo', 'error')
        return redirect(url_for('portfolio.import_orders'))

    selected_indexes = {int(i) for i in request.form.getlist('rows')}
    account_id = int(batch["account_id"])

    imported = 0
    missing_fx = []
    for index, row in enumerate(batch["rows"]):
        if index not in selected_indexes:
            continue
        if row["is_duplicate"] or row["is_unknown_symbol"]:
            continue

        executed_at = datetime.fromisoformat(row["executed_at"])
        fx_rate = fx_rate_to_cad_on(row["currency"], executed_at.date())
        if fx_rate is None:
            missing_fx.append(f'{row["currency"]}->CAD ({executed_at.date().isoformat()})')
            continue

        order = OrderModel(
            user_id=current_user.id,
            asset_id=row["asset_id"],
            account_id=account_id,
            type=OrderType(row["type"]),
            quantity=row["quantity"],
            price=row["price"],
            fees=row["fees"],
            currency=row["currency"],
            fx_rate_to_cad=fx_rate,
            executed_at=executed_at,
            broker=row["broker"],
            import_hash=row["import_hash"],
        )
        db.session.add(order)
        imported += 1

    db.session.commit()
    session.pop(f"import_batch:{batch_id}", None)
    flash(f'{imported} órdenes importadas', 'success')
    if missing_fx:
        flash(
            f'{len(missing_fx)} órdenes no se importaron porque no se encontró la tasa '
            f'{", ".join(sorted(set(missing_fx)))}.',
            'error',
        )
    return redirect(url_for('portfolio.list_orders'))
