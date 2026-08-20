from datetime import date

from src.extensions import scheduler
from src.models import UserModel
from src.resources.jobs._common import run_job
from src.services.portfolio import write_snapshots


def _snapshot_all_users():
    today = date.today()
    items = 0
    for user in UserModel.query.all():
        write_snapshots(user.id, today)
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
