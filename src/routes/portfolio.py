from collections import defaultdict

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.forms.AllocationTargetForm import AllocationTargetForm
from src.models import Account, AllocationTarget, Asset, DividendReceived
from src.services.portfolio import PortfolioService, fx_rate_to_cad_today

portfolio_bp = Blueprint('portfolio', __name__)

# Badge colours per account type, reusing the palette the rest of the app
# already speaks: registered accounts read as "sheltered", taxable ones don't.
ACCOUNT_BADGE_COLORS = {
    'TFSA': ('#e9efe9', '#1a7f4e'),
    'RRSP': ('#eceef2', '#4a6b8a'),
    'FHSA': ('#f0ece4', '#7d5ba6'),
    'MARGIN': ('#f3ece3', '#b98a2e'),
    'CASH': ('#f0eee8', '#6f6b60'),
}
DEFAULT_BADGE_COLOR = ('#f0eee8', '#6f6b60')

# Bar colours for the plan-vs-real rows, in order.
ALLOCATION_BAR_COLORS = ('#b3372b', '#b98a2e', '#1a7f4e', '#4a6b8a', '#7d5ba6', '#d9d5cb')

# Holdings whose asset carries no sector still have to land somewhere, and
# they're plannable like any other bucket.
UNCLASSIFIED_SECTOR = 'Sin clasificar'


def _sector_choices(user_id):
    """Sectors a target can be set on: the ones held, plus the ones already
    planned — so an existing target stays editable after its last holding in
    that sector is sold."""
    service = PortfolioService(user_id)
    asset_ids = [p['asset_id'] for p in service.get_positions_by_asset()]
    sectors = {
        asset.sector or UNCLASSIFIED_SECTOR
        for asset in (Asset.query.filter(Asset.id.in_(asset_ids)).all() if asset_ids else [])
    }
    sectors.update(
        row[0]
        for row in AllocationTarget.query.with_entities(AllocationTarget.sector)
        .filter_by(user_id=user_id)
        .all()
    )
    return sorted(sectors)


def _account_badges(accounts_by_asset, asset_id, accounts_by_id):
    """The account chips shown on a position row.

    Positions are pooled per asset (one row per asset, as the totals are), so
    an asset held in two accounts gets two chips rather than two rows.
    """
    badges = []
    for account_id in accounts_by_asset.get(asset_id, []):
        account = accounts_by_id.get(account_id)
        if account is None:
            continue
        background, color = ACCOUNT_BADGE_COLORS.get(account.type.value, DEFAULT_BADGE_COLOR)
        badges.append({'label': account.type.value, 'background': background, 'color': color})
    return badges


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

    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name.asc()).all()
    accounts_by_id = {a.id: a for a in accounts}
    # Which accounts actually still hold each asset — the by-asset rows pool
    # the lots together, so the account only survives in the lots.
    accounts_by_asset: dict[int, list] = {}
    for lot in service.get_positions():
        for lot_account_id, quantity in lot.quantity_by_account.items():
            if quantity <= 0:
                continue
            holders = accounts_by_asset.setdefault(lot.asset_id, [])
            if lot_account_id not in holders:
                holders.append(lot_account_id)

    portfolio_rows = []
    for p in positions:
        asset = assets_by_id.get(p['asset_id'])
        if asset is None:
            continue
        dividends = dividends_by_asset.get(p["asset_id"], 0.0)
        invested_cad = p["invested_cad"]
        portfolio_rows.append(
            {
                "symbol": asset.symbol,
                "name": asset.name,
                "exchange": asset.exchange,
                "detail_url": url_for('stocks.get_stock_detail', exchange=asset.exchange, symbol=asset.symbol),
                "accounts": _account_badges(accounts_by_asset, p["asset_id"], accounts_by_id),
                "actual_price": p["current_price"],
                "price": p["current_price"],
                "quantity": p["quantity"],
                "market_value": p["market_value_cad"],
                "adquisition_cost": invested_cad,
                "avg_price": p["avg_cost_cad"],
                "dividends": dividends,
                # Yield on cost: what the position pays today measured against
                # what it cost, not against what it's worth now.
                "yield_on_cost": (dividends / invested_cad * 100) if invested_cad else None,
                "profit": p["unrealized_pnl_cad"],
                "percent_return": p["percent_return"],
            }
        )
    portfolio_rows.sort(key=lambda row: row["market_value"] or 0.0, reverse=True)

    patrimony_cad = totals["patrimony_cad"] or 0.0
    invested_total = totals["total_invested_cad"] or 0.0
    dividends_total = totals["dividends_accum_cad"] or 0.0
    unrealized_total = patrimony_cad - invested_total
    # Headline return counts everything the portfolio produced: what the
    # positions gained on paper, the dividends banked and the trades closed.
    total_return_percent = (
        (unrealized_total + dividends_total + (totals["realized_pnl_cad"] or 0.0))
        / invested_total * 100
    ) if invested_total else None

    # Allocation target section — planned by sector, not by individual name.
    targets = {
        t.sector: t.target_percent
        for t in AllocationTarget.query.filter_by(user_id=current_user.id).all()
    }
    market_value_by_sector = defaultdict(float)
    for p in positions:
        asset = assets_by_id.get(p["asset_id"])
        if asset is None:
            continue
        market_value_by_sector[asset.sector or UNCLASSIFIED_SECTOR] += p["market_value_cad"] or 0.0

    allocation_rows = []
    if targets:
        # A held sector with no target is shown too, at meta 0% — an
        # unplanned position is exactly the deviation worth seeing.
        for sector in set(targets) | set(market_value_by_sector):
            market_value_cad = market_value_by_sector.get(sector, 0.0)
            current_percent = (market_value_cad / patrimony_cad * 100) if patrimony_cad else 0.0
            target_percent = targets.get(sector, 0.0)
            target_value_cad = target_percent / 100 * patrimony_cad
            amount_to_trade_cad = target_value_cad - market_value_cad
            allocation_rows.append(
                {
                    "sector": sector,
                    "current_percent": current_percent,
                    "target_percent": target_percent,
                    "has_target": sector in targets,
                    "deviation": current_percent - target_percent,
                    "amount_to_trade_cad": amount_to_trade_cad,
                    "amount_to_trade_abs_cad": abs(amount_to_trade_cad),
                }
            )
        allocation_rows.sort(key=lambda row: row["current_percent"], reverse=True)
        for index, row in enumerate(allocation_rows):
            row["color"] = ALLOCATION_BAR_COLORS[index % len(ALLOCATION_BAR_COLORS)]
    biggest_deviation = max(allocation_rows, key=lambda row: abs(row["deviation"]), default=None)

    allocation_target_form = AllocationTargetForm()
    allocation_target_form.sector.choices = [(s, s) for s in _sector_choices(current_user.id)]

    asset_labels = [row["symbol"] for row in portfolio_rows]
    asset_values = [row["market_value"] or 0.0 for row in portfolio_rows]

    context = {
        "portfolio": portfolio_rows,
        "accounts": accounts,
        "selected_account_id": account_id,
        "patrimony": patrimony_cad,
        "total_invested": invested_total,
        "realized_pnl": totals["realized_pnl_cad"],
        "dividends_accum": dividends_total,
        "unrealized_total": unrealized_total,
        "total_return_percent": total_return_percent,
        "total_yield_on_cost": (dividends_total / invested_total * 100) if invested_total else None,
        "usd_cad_rate": fx_rate_to_cad_today("USD"),
        "allocation_rows": allocation_rows,
        "biggest_deviation": biggest_deviation,
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
    form.sector.choices = [(s, s) for s in _sector_choices(current_user.id)]
    if form.validate_on_submit():
        try:
            target_percent = float(form.target_percent.data)
        except ValueError:
            flash('% objetivo inválido', 'error')
            return redirect(url_for('portfolio.portfolio'))

        sector = form.sector.data
        target = AllocationTarget.query.filter_by(user_id=current_user.id, sector=sector).first()
        if target is None:
            target = AllocationTarget(user_id=current_user.id, sector=sector, target_percent=target_percent)
            db.session.add(target)
        else:
            target.target_percent = target_percent
        db.session.commit()
        flash(f'Objetivo de alocación guardado para {sector}', 'success')
    else:
        flash('No se pudo guardar el objetivo de alocación', 'error')
    return redirect(url_for('portfolio.portfolio'))
