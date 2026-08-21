from dataclasses import dataclass
from datetime import date, datetime
import json
import time

from flask import current_app

from src.extensions import db
from src.models import Fundamentals, JobRun


@dataclass(frozen=True)
class JobResult:
    items_processed: int = 0
    errors: int = 0


@dataclass(frozen=True)
class OperationResult:
    success: bool
    items_processed: int = 0
    error: str | None = None


def _structured_log(**fields):
    current_app.logger.info(json.dumps(fields, default=str, sort_keys=True))


def run_operation(job_name, operation, fn, *, asset=None, provider=None, on_error=None):
    """Run and commit one isolated job operation, logging a structured result."""
    started = time.monotonic()
    log_fields = {
        'job_name': job_name,
        'asset_id': getattr(asset, 'id', None),
        'symbol': getattr(asset, 'symbol', None),
        'provider': provider,
        'operation': operation,
    }
    try:
        value = fn()
        db.session.commit()
        items = value if isinstance(value, int) and not isinstance(value, bool) else 1
        _structured_log(
            **log_fields, status='success',
            duration=round(time.monotonic() - started, 4), error=None,
        )
        return OperationResult(True, items)
    except Exception as exc:
        db.session.rollback()
        if on_error is not None:
            try:
                on_error(exc)
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception('Could not persist operation failure metadata')
        _structured_log(
            **log_fields, status='error',
            duration=round(time.monotonic() - started, 4), error=str(exc),
        )
        return OperationResult(False, 0, str(exc))


def run_job(job_name, fn):
    """Wrap a job body with JobRun bookkeeping (started/finished/status/items).

    `fn` runs inside an active app context and may return either an item count
    or JobResult. Asset/source operations commit independently through
    run_operation; a partial outage is recorded without discarding successful
    siblings or killing the scheduler process.
    """
    job_run = JobRun(job=job_name, started_at=datetime.utcnow(), status="running")
    db.session.add(job_run)
    db.session.commit()

    try:
        result = fn()
        db.session.commit()
        if isinstance(result, JobResult):
            job_run.status = "partial" if result.errors else "success"
            job_run.items_processed = result.items_processed
            job_run.error = (
                f"{result.errors} isolated operation(s) failed" if result.errors else None
            )
        else:
            job_run.status = "success"
            job_run.items_processed = result
    except Exception as exc:
        db.session.rollback()
        job_run.status = "failed"
        job_run.error = str(exc)
    finally:
        job_run.finished_at = datetime.utcnow()
        db.session.commit()

    return job_run


_SNAPSHOT_CARRY_FORWARD_COLUMNS = [
    column.name for column in Fundamentals.__table__.columns
    if column.name not in ('id', 'asset_id', 'as_of_date')
]


def get_or_create_snapshot(asset_id: int, as_of_date: date | None = None) -> Fundamentals:
    """Get or create one idempotent Fundamentals row for a date.

    A newly created row is seeded from the asset's most recent prior
    snapshot, so a field a provider fails to return today doesn't blank out
    the last non-null value the app actually observed for it.
    """
    today = as_of_date or date.today()
    snapshot = Fundamentals.query.filter_by(asset_id=asset_id, as_of_date=today).first()
    if snapshot is None:
        snapshot = Fundamentals(asset_id=asset_id, as_of_date=today)
        previous = (
            Fundamentals.query
            .filter(Fundamentals.asset_id == asset_id, Fundamentals.as_of_date < today)
            .order_by(Fundamentals.as_of_date.desc())
            .first()
        )
        if previous is not None:
            for column in _SNAPSHOT_CARRY_FORWARD_COLUMNS:
                setattr(snapshot, column, getattr(previous, column))
        db.session.add(snapshot)
    return snapshot
