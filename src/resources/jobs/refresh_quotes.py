from src.extensions import db, scheduler
from src.models import Asset, OrderModel
from src.resources.jobs._common import get_or_create_snapshot, run_job
from src.services.market_data import get_provider


def refresh_asset_quote(asset, provider=None) -> bool:
    """Write today's price for one asset, returning whether it succeeded.

    Kept as a small reusable operation so a newly-added holding can receive
    its first price immediately instead of waiting up to 15 minutes for the
    scheduled sweep.  The caller owns the transaction.
    """
    provider = provider or get_provider()
    quote = provider.get_quote(asset.yahoo_symbol)
    price = quote.get("price") if quote else None
    if price is None:
        return False
    snapshot = get_or_create_snapshot(asset.id)
    snapshot.price = price
    return True


def _refresh_held_quotes():
    provider = get_provider()
    asset_ids = [row[0] for row in db.session.query(OrderModel.asset_id).distinct().all()]
    if not asset_ids:
        return 0

    items = 0
    for asset in Asset.query.filter(Asset.id.in_(asset_ids)).all():
        if refresh_asset_quote(asset, provider):
            items += 1
    return items


@scheduler.task('interval', id='refresh_quotes', minutes=15)
def refresh_quotes():
    """Intraday, price-only refresh — only for assets currently held in at least one order."""
    with scheduler.app.app_context():
        run_job('refresh_quotes', _refresh_held_quotes)
