from datetime import date, timedelta

from src.extensions import scheduler
from src.resources.jobs._common import run_job
from src.services.fx import fetch_rates_to_cad


def _refresh_usdcad():
    today = date.today()
    rows = fetch_rates_to_cad("USD", today - timedelta(days=7), today)
    return len(rows)


@scheduler.task('cron', id='refresh_fx', hour=18, minute=30, timezone='America/Toronto')
def refresh_fx():
    """Daily USD/CAD rate from the Bank of Canada Valet API."""
    with scheduler.app.app_context():
        run_job('refresh_fx', _refresh_usdcad)
