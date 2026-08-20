from datetime import date

from src.extensions import db, scheduler
from src.models import Account, PortfolioSnapshotModel, UserModel
from src.resources.jobs._common import run_job
from src.services.portfolio import PortfolioService


def _write_snapshot(user_id, today, account_id, totals):
    row = PortfolioSnapshotModel.query.filter_by(
        user_id=user_id, date=today, account_id=account_id
    ).first()
    if row is None:
        row = PortfolioSnapshotModel(user_id=user_id, date=today, account_id=account_id)
        db.session.add(row)
    row.patrimony_cad = totals["patrimony_cad"]
    row.total_invested_cad = totals["total_invested_cad"]
    row.dividends_accum_cad = totals["dividends_accum_cad"]


def _snapshot_all_users():
    today = date.today()
    items = 0
    for user in UserModel.query.all():
        service = PortfolioService(user.id)
        service.sync_suggested_dividends()
        _write_snapshot(user.id, today, None, service.get_totals())
        for account in Account.query.filter_by(user_id=user.id).all():
            _write_snapshot(user.id, today, account.id, service.get_totals(account_id=account.id))
        items += 1
    return items


@scheduler.task('cron', id='refresh_snapshots', hour=20, minute=0, timezone='America/Toronto')
def refresh_snapshots():
    """Daily net-worth snapshot (total + one row per account) for every user.

    Scheduled after refresh_fundamentals (18:00) and refresh_fx (18:30) so
    today's prices/FX are already in place for CAD conversion.
    """
    with scheduler.app.app_context():
        run_job('refresh_snapshots', _snapshot_all_users)
