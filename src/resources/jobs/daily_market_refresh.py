from datetime import date, timedelta

from src.extensions import db, scheduler
from src.resources.jobs._common import JobResult, run_job, run_operation
from src.services.fx import fetch_rates_to_cad
from src.services.job_policies import relevant_assets
from src.services.market_data import get_provider
from src.services.market_prices import refresh_asset_price
from src.services.market_strip import refresh_market_indicators

JOB_NAME = 'daily_market_refresh'


def _refresh_daily_asset(asset, provider):
    result = refresh_asset_price(asset, provider, cooldown_minutes=0)
    if result.status == 'failed':
        # Persist the counter before run_operation rolls back the exception
        # used to mark this isolated subtask as failed.
        db.session.commit()
        raise RuntimeError('no daily price available')
    return 1 if result.refreshed else 0


def _daily_market_refresh():
    provider = get_provider()
    processed = errors = 0
    for asset in relevant_assets():
        outcome = run_operation(
            JOB_NAME,
            'daily_price',
            lambda asset=asset: _refresh_daily_asset(asset, provider),
            asset=asset,
            provider=provider.__class__.__name__,
        )
        processed += outcome.items_processed
        errors += not outcome.success

    today = date.today()
    for operation, provider_name, fn in (
        ('usd_cad', 'BankOfCanada', lambda: len(fetch_rates_to_cad('USD', today - timedelta(days=7), today))),
        ('market_strip', 'Yahoo/BankOfCanada', refresh_market_indicators),
    ):
        outcome = run_operation(JOB_NAME, operation, fn, provider=provider_name)
        processed += outcome.items_processed
        errors += not outcome.success
    return JobResult(processed, errors)


@scheduler.task(
    'cron', id=JOB_NAME, day_of_week='mon-fri', hour=17, minute=15,
    timezone='America/Toronto',
    misfire_grace_time=3600, coalesce=True, max_instances=1,
)
def daily_market_refresh():
    """Daily prices, indices, USD/CAD and BoC policy rate after market close."""
    with scheduler.app.app_context():
        run_job(JOB_NAME, _daily_market_refresh)
