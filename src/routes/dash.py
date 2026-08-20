from flask import flash, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.services.dashboard import DashboardService
from src.services.portfolio import fx_rate_to_cad_today, write_snapshots
from .portfolio import portfolio_bp


@portfolio_bp.route('/dashboard', methods=['GET'])
@login_required
def dash_page():
    service = DashboardService(current_user.id)
    context = {
        'kpis': service.kpis(),
        'equity': service.equity_series(),
        'has_equity_history': service.has_equity_history(),
        'sectors': service.sector_allocation(),
        'currencies': service.currency_allocation(),
        'contributions': service.monthly_contributions(),
        'top_positions': service.top_positions(),
        'events': service.upcoming_events(),
        'market': service.market_status(),
        'usd_cad_rate': fx_rate_to_cad_today('USD'),
        'today': service.today,
    }
    return render_template('dash.html', warnings=sorted(set(service.warnings)), **context)


@portfolio_bp.route('/dashboard/equity/month', methods=['GET'])
@login_required
def dashboard_monthly_equity():
    """Daily month-to-date portfolio history for the 1M chart range."""
    return jsonify(DashboardService(current_user.id).monthly_equity_series())


@portfolio_bp.route('/dashboard/recalculate', methods=['POST'])
@login_required
def recalculate_dashboard():
    """Take today's snapshot now rather than waiting for the nightly job.

    The KPI band and the positions always read live prices, so this doesn't
    change them — what it moves is the equity curve, which is drawn from
    snapshots and would otherwise stop at yesterday.
    """
    write_snapshots(current_user.id)
    db.session.commit()
    flash('Snapshot de hoy recalculado con los últimos precios', 'success')
    return redirect(url_for('portfolio.dash_page'))
