from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.forms.PortfolioPlanForm import PortfolioPlanForm
from src.models import (
    ASSET_CATEGORY_LABELS,
    Account,
    Asset,
    DividendReceived,
    PortfolioPlan,
)
from src.services.portfolio import PortfolioService, fx_rate_to_cad_today
from src.services.portfolio_analytics import PortfolioAnalyticsService
from src.services.market_data import get_provider
from src.services.market_prices import latest_price_updated_at, refresh_asset_price

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
                "category": asset.category,
                "category_label": ASSET_CATEGORY_LABELS[asset.category],
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

    analytics = PortfolioAnalyticsService(current_user.id)
    plan = PortfolioPlan.query.filter_by(user_id=current_user.id).first()
    plan_form = PortfolioPlanForm(obj=plan)
    strategic_allocation = analytics.allocation(positions, assets_by_id, plan)
    dividend_chart = analytics.dividends_by_asset(assets_by_id)
    performance_chart = analytics.performance()

    portfolio_asset_ids = [row['asset_id'] for row in positions]

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
        "asset_types": asset_labels,
        "asset_allocation": asset_values,
        "plan_form": plan_form,
        "plan_is_saved": plan is not None,
        "strategic_allocation": strategic_allocation,
        "dividend_chart": dividend_chart,
        "performance_chart": performance_chart,
        "warnings": service.warnings,
        "prices_updated_at": latest_price_updated_at(portfolio_asset_ids),
    }

    return render_template('portfolio.html', **context)


@portfolio_bp.route('/portfolio/refresh-prices', methods=['POST'])
@login_required
def refresh_prices():
    """Refresh only stale global prices used by the current user's holdings."""
    service = PortfolioService(current_user.id)
    asset_ids = [row['asset_id'] for row in service.get_positions_by_asset()]
    assets = Asset.query.filter(Asset.id.in_(asset_ids)).order_by(Asset.id.asc()).all() if asset_ids else []
    provider = get_provider()
    refreshed = reused = failed = 0

    for asset in assets:
        try:
            result = refresh_asset_price(asset, provider)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            failed += 1
            current_app.logger.warning(
                'Manual price refresh failed for asset %s (%s): %s',
                asset.id, asset.symbol, exc,
            )
            continue
        if result.status == 'refreshed':
            refreshed += 1
        elif result.status == 'fresh':
            reused += 1
        else:
            failed += 1

    if failed:
        flash(
            f'Precios actualizados: {refreshed}; reutilizados: {reused}; sin datos: {failed}.',
            'info',
        )
    else:
        flash(f'Precios actualizados: {refreshed}; reutilizados por cooldown: {reused}.', 'success')
    return redirect(url_for('portfolio.portfolio'))


@portfolio_bp.route('/portfolio/plan', methods=['POST'])
@login_required
def set_portfolio_plan():
    form = PortfolioPlanForm()
    if not form.validate_on_submit():
        flash('Revisá los porcentajes y el saldo de cash', 'error')
        return redirect(url_for('portfolio.portfolio') + '#portfolio-ideal')

    percentages = (
        form.equity_etf_percent.data,
        form.reit_percent.data,
        form.fixed_income_percent.data,
        form.crypto_percent.data,
        form.cash_percent.data,
    )
    if abs(sum(percentages) - 100) > 0.01:
        flash('El portafolio ideal debe sumar exactamente 100%', 'error')
        return redirect(url_for('portfolio.portfolio') + '#portfolio-ideal')

    plan = PortfolioPlan.query.filter_by(user_id=current_user.id).first()
    if plan is None:
        plan = PortfolioPlan(user_id=current_user.id)
        db.session.add(plan)

    plan.equity_etf_percent = float(form.equity_etf_percent.data)
    plan.reit_percent = float(form.reit_percent.data)
    plan.fixed_income_percent = float(form.fixed_income_percent.data)
    plan.crypto_percent = float(form.crypto_percent.data)
    plan.cash_percent = float(form.cash_percent.data)
    plan.cash_balance_cad = float(form.cash_balance_cad.data or 0)
    db.session.commit()
    flash('Tu portafolio ideal quedó guardado', 'success')
    return redirect(url_for('portfolio.portfolio') + '#portfolio-ideal')
