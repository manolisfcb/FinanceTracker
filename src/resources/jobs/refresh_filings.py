from src.extensions import scheduler
from src.resources.jobs._common import run_job
from src.services.company_data import held_assets, ingest_filings


def _refresh_filings():
    items = 0
    for asset in held_assets():
        items += ingest_filings(asset)
    return items


@scheduler.task('cron', id='refresh_filings', hour=19, minute=0, timezone='America/Toronto')
def refresh_filings():
    """SEC EDGAR filings for held US assets.

    Split from refresh_dividends (which covers everything Yahoo serves) so a
    Yahoo outage can't take EDGAR down with it, and vice versa.
    """
    with scheduler.app.app_context():
        run_job('refresh_filings', _refresh_filings)
