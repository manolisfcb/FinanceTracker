from src.extensions import scheduler
from src.models import Asset
from src.resources.jobs._common import get_or_create_snapshot, run_job
from src.services.market_data import get_provider


def _refresh_all():
    provider = get_provider()
    items = 0
    for asset in Asset.query.filter_by(is_active=True).all():
        data = provider.get_fundamentals(asset.yahoo_symbol)
        if not data:
            continue
        snapshot = get_or_create_snapshot(asset.id)
        for key, value in data.items():
            setattr(snapshot, key, value)
        items += 1
    return items


@scheduler.task('cron', id='refresh_fundamentals', hour=18, minute=0, timezone='America/Toronto')
def refresh_fundamentals():
    """Daily fundamentals snapshot for every active Asset, after market close."""
    with scheduler.app.app_context():
        run_job('refresh_fundamentals', _refresh_all)
