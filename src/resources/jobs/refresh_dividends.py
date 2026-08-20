from src.extensions import scheduler
from src.resources.jobs._common import run_job
from src.services.company_data import held_assets, ingest_calendar, ingest_dividends
from src.services.market_data import get_provider


def _refresh_held_dividends():
    provider = get_provider()
    items = 0
    for asset in held_assets():
        ingest_dividends(asset, provider)
        ingest_calendar(asset, provider)
        items += 1
    return items


@scheduler.task('cron', id='refresh_dividends', hour=17, minute=30, timezone='America/Toronto')
def refresh_dividends():
    """Dividend history, the next announced ex-date and the next earnings
    date for held assets.

    Runs before refresh_snapshots (20:00), which turns this history into
    per-user suggested DividendReceived rows.
    """
    with scheduler.app.app_context():
        run_job('refresh_dividends', _refresh_held_dividends)
