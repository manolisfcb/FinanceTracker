from datetime import date

from src.extensions import scheduler
from src.models import UserModel
from src.resources.jobs._common import JobResult, run_job, run_operation
from src.services.portfolio import write_snapshots


JOB_NAME = 'daily_portfolio_snapshots'


def _snapshot_all_users():
    today = date.today()
    items = 0
    for user in UserModel.query.order_by(UserModel.id.asc()).all():
        write_snapshots(user.id, today)
        items += 1
    return items


def _snapshot_user(user_id, today):
    write_snapshots(user_id, today)
    return 1


def _daily_portfolio_snapshots():
    today = date.today()
    processed = errors = 0
    for user in UserModel.query.order_by(UserModel.id.asc()).all():
        outcome = run_operation(
            JOB_NAME, 'portfolio_snapshot',
            lambda user=user: _snapshot_user(user.id, today),
            provider='database',
        )
        processed += outcome.items_processed
        errors += not outcome.success
    return JobResult(processed, errors)


@scheduler.task(
    'cron', id=JOB_NAME, hour=20, minute=0, timezone='America/Toronto',
    misfire_grace_time=3600, coalesce=True, max_instances=1,
)
def daily_portfolio_snapshots():
    """Idempotent user/account snapshots using only persisted prices and FX."""
    with scheduler.app.app_context():
        run_job(JOB_NAME, _daily_portfolio_snapshots)
