from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.forms.AllocationTargetForm import AllocationTargetForm
from src.models import Account, AllocationTarget, Asset, DividendReceived
from src.resources.orders_import.registry import resolve_asset_id
from src.services.portfolio import PortfolioService

portfolio_bp = Blueprint('portfolio', __name__)


@portfolio_bp.route('/portfolio', methods=['GET'])
@login_required
def portfolio():
    account_id = request.args.get('account_id', type=int)

    service = PortfolioService(current_user.id)
    positions = service.get_positions_by_asset()
    totals = service.get_totals(account_id=account_id)

    assets_by_id = {a.id: a for a in Asset.query.filter(Asset.id.in_([p['asset_id'] for p in positions])).all()} if positions else {}
    dividends_by_asset = {}
    for row in DividendReceived.query.filter_by(user_id=current_user.id, confirmed=True).all():
        dividends_by_asset[row.asset_id] = dividends_by_asset.get(row.asset_id, 0.0) + row.total_amount

    portfolio_rows = []
    for p in positions:
        asset = assets_by_id.get(p['asset_id'])
        if asset is None:
            continue
        portfolio_rows.append(
            {
                "symbol": asset.symbol,
                "name": asset.name,
                "actual_price": p["current_price"],
                "price": p["current_price"],
                "quantity": p["quantity"],
                "adquisition_cost": p["invested_cad"],
                "avg_price": p["avg_cost_cad"],
                "profit": p["unrealized_pnl_cad"],
                "percent_return": p["percent_return"],
                "percent_return_dividends": dividends_by_asset.get(p["asset_id"], 0.0),
            }
        )

    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name.asc()).all()

    # Allocation target section
    targets = AllocationTarget.query.filter_by(user_id=current_user.id).all()
    targets_by_asset = {t.asset_id: t.target_percent for t in targets}
    patrimony_cad = totals["patrimony_cad"] or 0.0
    allocation_rows = []
    for p in positions:
        asset = assets_by_id.get(p["asset_id"])
        if asset is None or p["asset_id"] not in targets_by_asset:
            continue
        market_value_cad = p["market_value_cad"]
        current_percent = (market_value_cad / patrimony_cad * 100) if patrimony_cad else 0.0
        target_percent = targets_by_asset[p["asset_id"]]
        deviation = current_percent - target_percent
        target_value_cad = target_percent / 100 * patrimony_cad
        amount_to_trade_cad = target_value_cad - market_value_cad
        allocation_rows.append(
            {
                "symbol": asset.symbol,
                "current_percent": current_percent,
                "target_percent": target_percent,
                "deviation": deviation,
                "amount_to_trade_cad": amount_to_trade_cad,
                "amount_to_trade_abs_cad": abs(amount_to_trade_cad),
            }
        )

    allocation_target_form = AllocationTargetForm()

    asset_labels = [row["symbol"] for row in portfolio_rows]
    asset_values = [(row["actual_price"] or 0) * row["quantity"] for row in portfolio_rows]

    context = {
        "portfolio": portfolio_rows,
        "accounts": accounts,
        "selected_account_id": account_id,
        "patrimony": totals["patrimony_cad"],
        "total_invested": totals["total_invested_cad"],
        "realized_pnl": totals["realized_pnl_cad"],
        "dividends_accum": totals["dividends_accum_cad"],
        "allocation_rows": allocation_rows,
        "allocation_target_form": allocation_target_form,
        "asset_types": asset_labels,
        "asset_allocation": asset_values,
        "warnings": service.warnings,
    }

    return render_template('portfolio.html', **context)


@portfolio_bp.route('/portfolio/allocation-targets', methods=['POST'])
@login_required
def set_allocation_target():
    form = AllocationTargetForm()
    if form.validate_on_submit():
        asset_id = resolve_asset_id(form.asset_symbol.data)
        if asset_id is None:
            flash(f'No se encontró el activo "{form.asset_symbol.data}"', 'error')
            return redirect(url_for('portfolio.portfolio'))

        try:
            target_percent = float(form.target_percent.data)
        except ValueError:
            flash('% objetivo inválido', 'error')
            return redirect(url_for('portfolio.portfolio'))

        target = AllocationTarget.query.filter_by(user_id=current_user.id, asset_id=asset_id).first()
        if target is None:
            target = AllocationTarget(user_id=current_user.id, asset_id=asset_id, target_percent=target_percent)
            db.session.add(target)
        else:
            target.target_percent = target_percent
        db.session.commit()
        flash('Objetivo de alocación guardado', 'success')
    return redirect(url_for('portfolio.portfolio'))
