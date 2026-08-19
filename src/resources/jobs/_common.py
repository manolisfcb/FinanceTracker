from datetime import date, datetime

from src.extensions import db
from src.models import Fundamentals, JobRun


def run_job(job_name, fn):
    """Wrap a job body with JobRun bookkeeping (started/finished/status/items).

    `fn` must run inside an already-active app context and return the number
    of items it processed. On failure, all of `fn`'s uncommitted DB changes
    are rolled back so a run is atomic (all-or-nothing), and the error is
    recorded on the JobRun row instead of raising, so a bad run doesn't kill
    the scheduler process.
    """
    job_run = JobRun(job=job_name, started_at=datetime.utcnow(), status="running")
    db.session.add(job_run)
    db.session.commit()

    try:
        items = fn()
        db.session.commit()
        job_run.status = "success"
        job_run.items_processed = items
    except Exception as exc:
        db.session.rollback()
        job_run.status = "failed"
        job_run.error = str(exc)
    finally:
        job_run.finished_at = datetime.utcnow()
        db.session.commit()

    return job_run


def get_or_create_snapshot(asset_id: int) -> Fundamentals:
    """Today's Fundamentals row for an asset, creating an empty one if needed
    so refresh_quotes (intraday, price-only) and refresh_fundamentals (daily,
    full metrics) can both write into the same day's snapshot regardless of
    which one runs first."""
    today = date.today()
    snapshot = Fundamentals.query.filter_by(asset_id=asset_id, as_of_date=today).first()
    if snapshot is None:
        snapshot = Fundamentals(asset_id=asset_id, as_of_date=today)
        db.session.add(snapshot)
    return snapshot
