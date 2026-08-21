"""Selection and freshness rules for scheduled asset work."""
from collections import defaultdict
from datetime import datetime, timedelta

from src.models import Asset, AssetType, ListingStatus, OrderModel, OrderType
from src.services.company_data import US_EXCHANGES

RECENTLY_VIEWED_DAYS = 30
FUNDAMENTALS_FRESH_DAYS = 7
DIVIDENDS_FRESH_HOURS = 24
FILINGS_FRESH_HOURS = 24
NEWS_FRESH_HOURS = 24


def currently_held_asset_ids() -> set[int]:
    balances = defaultdict(float)
    for asset_id, order_type, quantity in OrderModel.query.with_entities(
        OrderModel.asset_id, OrderModel.type, OrderModel.quantity
    ):
        balances[asset_id] += quantity if order_type == OrderType.BUY else -quantity
    return {asset_id for asset_id, quantity in balances.items() if quantity > 0}


def watchlist_asset_ids() -> set[int]:
    """Extension point for the future watchlist model."""
    return set()


def recently_viewed_asset_ids(now=None) -> set[int]:
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=RECENTLY_VIEWED_DAYS)
    return {
        asset_id for (asset_id,) in
        Asset.query.filter(Asset.last_viewed_at >= cutoff).with_entities(Asset.id).all()
    }


def relevant_assets(now=None) -> list[Asset]:
    ids = currently_held_asset_ids() | watchlist_asset_ids() | recently_viewed_asset_ids(now)
    if not ids:
        return []
    return (
        Asset.query.filter(
            Asset.id.in_(ids),
            Asset.listing_status.notin_([ListingStatus.DELISTED, ListingStatus.SUSPENDED]),
        )
        .order_by(Asset.id.asc())
        .all()
    )


def fundamentals_eligible(asset) -> bool:
    return (
        asset.asset_type in {AssetType.STOCK, AssetType.ETF}
        and asset.listing_status == ListingStatus.ACTIVE
        and asset.fundamentals_enabled is True
    )


def fundamentals_universe() -> list[Asset]:
    """Every asset eligible for a fundamentals snapshot.

    Unlike dividends/filings/news — genuinely per-holding jobs — the
    screener lists the whole asset universe and needs real numbers for all
    of it, not just what's held or recently viewed. Mirrors
    `fundamentals_eligible` as a query rather than a per-asset predicate.
    """
    return (
        Asset.query.filter(
            Asset.asset_type.in_([AssetType.STOCK, AssetType.ETF]),
            Asset.listing_status == ListingStatus.ACTIVE,
            Asset.fundamentals_enabled.is_(True),
        )
        .order_by(Asset.id.asc())
        .all()
    )


def _older_than(value, delta, now) -> bool:
    return value is None or value < now - delta


def needs_fundamentals_refresh(asset, now=None) -> bool:
    now = now or datetime.utcnow()
    return fundamentals_eligible(asset) and _older_than(
        asset.last_fundamentals_refresh_at, timedelta(days=FUNDAMENTALS_FRESH_DAYS), now,
    )


def needs_dividend_refresh(asset, now=None) -> bool:
    now = now or datetime.utcnow()
    return fundamentals_eligible(asset) and _older_than(
        asset.last_dividend_refresh_at, timedelta(hours=DIVIDENDS_FRESH_HOURS), now,
    )


def needs_filings_refresh(asset, now=None) -> bool:
    now = now or datetime.utcnow()
    return (
        fundamentals_eligible(asset)
        and asset.exchange in US_EXCHANGES
        and _older_than(asset.last_filings_refresh_at, timedelta(hours=FILINGS_FRESH_HOURS), now)
    )


def needs_news_refresh(asset, now=None) -> bool:
    now = now or datetime.utcnow()
    return _older_than(asset.last_news_refresh_at, timedelta(hours=NEWS_FRESH_HOURS), now)
