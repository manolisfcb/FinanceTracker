from collections import defaultdict

from flask import render_template
from flask_login import current_user, login_required

from src.models import Asset, OrderModel, OrderType, PortfolioSnapshotModel
from src.services.portfolio import PortfolioService
from .portfolio import portfolio_bp


@portfolio_bp.route('/dashboard', methods=['GET'])
@login_required
def dash_page():
    service = PortfolioService(current_user.id)
    positions = service.get_positions_by_asset()
    totals = service.get_totals()

    snapshots = (
        PortfolioSnapshotModel.query.filter_by(user_id=current_user.id, account_id=None)
        .order_by(PortfolioSnapshotModel.date.asc())
        .all()
    )
    historical_labels = [s.date.strftime('%Y-%m-%d') for s in snapshots]
    historical_patrimony = [s.patrimony_cad for s in snapshots]

    contributions_by_month = defaultdict(float)
    orders = OrderModel.query.filter_by(user_id=current_user.id, type=OrderType.BUY).all()
    for order in orders:
        month_key = order.executed_at.strftime('%Y-%m')
        contributions_by_month[month_key] += (order.quantity * order.price + order.fees) * order.fx_rate_to_cad
    contribution_months = sorted(contributions_by_month.keys())
    contributions_data = [contributions_by_month[m] for m in contribution_months]

    assets_by_id = {a.id: a for a in Asset.query.filter(Asset.id.in_([p['asset_id'] for p in positions])).all()} if positions else {}
    by_sector = defaultdict(float)
    for p in positions:
        asset = assets_by_id.get(p['asset_id'])
        if asset is None:
            continue
        by_sector[asset.sector or 'Sin clasificar'] += p['market_value_cad'] or 0.0

    performance = (
        ((totals['patrimony_cad'] or 0) - (totals['total_invested_cad'] or 0)) / totals['total_invested_cad'] * 100
        if totals['total_invested_cad']
        else 0.0
    )

    context = {
        "totals": {
            "performance": round(performance, 2),
            "patrimonio": totals["patrimony_cad"],
            "costo_adquisicion": totals["total_invested_cad"],
            "proventos_acumulados": totals["dividends_accum_cad"],
            "lucro_operaciones": totals["realized_pnl_cad"],
            "total_contribuicoes": sum(contributions_data),
        },
        "historical_labels": historical_labels,
        "historical_data": historical_patrimony,
        "contributions_labels": contribution_months,
        "contributions_data": contributions_data,
        "portfolio_labels": list(by_sector.keys()),
        "portfolio_data": list(by_sector.values()),
    }
    return render_template('dash.html', **context)
