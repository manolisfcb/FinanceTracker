from src.extensions import scheduler
from src.models import Asset
from src.resources.jobs._common import get_or_create_snapshot, run_job
from src.services.fundamentals import carry_forward_statements, derive_indicators
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
        # The statement figures behind P/EBIT, ROIC and deuda neta/EBITDA
        # aren't fetched here (two more Yahoo calls times the whole universe
        # for data that moves quarterly) — they ride forward from the last
        # snapshot that has them, so the ratios stay in step with today's
        # market cap. Assets nobody has opened yet get them on first view.
        carry_forward_statements(asset, snapshot)
        derive_indicators(snapshot)
        items += 1
    return items


@scheduler.task('cron', id='refresh_fundamentals', hour=18, minute=0, timezone='America/Toronto')
def refresh_fundamentals():
    """Daily fundamentals snapshot for every active Asset, after market close."""
    with scheduler.app.app_context():
        run_job('refresh_fundamentals', _refresh_all)
