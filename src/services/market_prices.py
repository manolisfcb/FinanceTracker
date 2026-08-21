"""Global daily prices, provider cooldown and per-asset deduplication."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import threading

from sqlalchemy import text

from src.extensions import db
from src.models import AssetPrice, ListingStatus
from src.resources.jobs._common import get_or_create_snapshot
from src.services.market_data import get_provider

PRICE_REFRESH_COOLDOWN_MINUTES = 15
MARKET_DATA_FAILURES_BEFORE_UNKNOWN = 3
_ADVISORY_LOCK_NAMESPACE = 8142
_local_locks: dict[int, threading.Lock] = {}
_local_locks_guard = threading.Lock()


@dataclass(frozen=True)
class PriceRefreshResult:
    status: str
    price: AssetPrice | None

    @property
    def refreshed(self) -> bool:
        return self.status == 'refreshed'


def latest_asset_price(asset_id: int) -> AssetPrice | None:
    return (
        AssetPrice.query.filter_by(asset_id=asset_id)
        .order_by(AssetPrice.price_date.desc(), AssetPrice.updated_at.desc())
        .first()
    )


def latest_price_updated_at(asset_ids) -> datetime | None:
    ids = list(asset_ids)
    if not ids:
        return None
    return (
        db.session.query(db.func.max(AssetPrice.updated_at))
        .filter(AssetPrice.asset_id.in_(ids))
        .scalar()
    )


def price_is_stale(row: AssetPrice | None, now=None, cooldown_minutes=None) -> bool:
    if row is None:
        return True
    now = now or datetime.utcnow()
    cooldown_minutes = (
        PRICE_REFRESH_COOLDOWN_MINUTES if cooldown_minutes is None else cooldown_minutes
    )
    return row.updated_at < now - timedelta(minutes=cooldown_minutes)


@contextmanager
def asset_refresh_lock(asset_id: int):
    """Cross-process PostgreSQL lock; process-local fallback for SQLite."""
    if db.session.get_bind().dialect.name == 'postgresql':
        db.session.execute(
            text('SELECT pg_advisory_xact_lock(:namespace, :asset_id)'),
            {'namespace': _ADVISORY_LOCK_NAMESPACE, 'asset_id': asset_id},
        )
        yield
        return

    with _local_locks_guard:
        lock = _local_locks.setdefault(asset_id, threading.Lock())
    with lock:
        yield


def record_market_data_failure(asset, now=None) -> None:
    now = now or datetime.utcnow()
    asset.market_data_failures = (asset.market_data_failures or 0) + 1
    asset.last_market_data_failure_at = now
    if (
        asset.market_data_failures >= MARKET_DATA_FAILURES_BEFORE_UNKNOWN
        and asset.listing_status == ListingStatus.ACTIVE
    ):
        asset.listing_status = ListingStatus.UNKNOWN


def _record_market_data_success(asset, now) -> None:
    asset.market_data_failures = 0
    asset.last_market_data_success_at = now
    if asset.listing_status == ListingStatus.UNKNOWN:
        asset.listing_status = ListingStatus.ACTIVE


def _upsert_daily_price(asset, payload, now) -> AssetPrice:
    price_date = payload.get('date') or date.today()
    if isinstance(price_date, str):
        price_date = date.fromisoformat(price_date)
    row = AssetPrice.query.filter_by(asset_id=asset.id, price_date=price_date).first()
    if row is None:
        row = AssetPrice(asset_id=asset.id, price_date=price_date)
        db.session.add(row)
    row.open = payload.get('open')
    row.close = payload['close']
    row.previous_close = payload.get('previous_close')
    row.high = payload.get('high')
    row.low = payload.get('low')
    row.volume = payload.get('volume')
    row.updated_at = now

    # Transitional compatibility: several analysis screens still read the
    # price column co-located with Fundamentals. AssetPrice is authoritative.
    # get_or_create_snapshot seeds a new row from the prior day's snapshot,
    # so this doesn't blank out fundamentals the day's later sweep hasn't
    # refreshed yet.
    snapshot = get_or_create_snapshot(asset.id, price_date)
    snapshot.price = row.close

    currency = payload.get('currency')
    if currency in {'CAD', 'USD'}:
        asset.currency = currency
    _record_market_data_success(asset, now)
    return row


def refresh_asset_price(asset, provider=None, *, now=None, cooldown_minutes=None):
    """Refresh one asset unless its global price is inside the cooldown."""
    now = now or datetime.utcnow()
    provider = provider or get_provider()
    with asset_refresh_lock(asset.id):
        current = latest_asset_price(asset.id)
        if not price_is_stale(current, now, cooldown_minutes):
            return PriceRefreshResult('fresh', current)

        try:
            payload = provider.get_daily_price(asset.yahoo_symbol)
        except Exception:
            record_market_data_failure(asset, now)
            return PriceRefreshResult('failed', current)
        if not payload or payload.get('close') is None:
            record_market_data_failure(asset, now)
            return PriceRefreshResult('failed', current)
        return PriceRefreshResult('refreshed', _upsert_daily_price(asset, payload, now))
