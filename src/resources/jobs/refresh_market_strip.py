from src.extensions import scheduler
from src.resources.jobs._common import run_job
from src.services.market_strip import refresh_market_indicators


@scheduler.task('interval', id='refresh_market_strip', minutes=15, misfire_grace_time=300)
def refresh_market_strip():
    """Index levels, USD/CAD and the BoC rate shown on the site-wide strip."""
    with scheduler.app.app_context():
        run_job('refresh_market_strip', refresh_market_indicators)
