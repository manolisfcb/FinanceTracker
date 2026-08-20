import re

from flask import current_app, has_app_context

from src.data.asset_catalog import CRYPTO_ASSETS, ETF_ASSETS
from src.extensions import db
from src.models import Asset
from src.resources.orders_import.ibkr import IBKRFlexImporter
from src.resources.orders_import.questrade import QuestradeCSVImporter
from src.resources.orders_import.wealthsimple import WealthsimpleCSVImporter

IMPORTERS = {
    "questrade": QuestradeCSVImporter,
    "wealthsimple": WealthsimpleCSVImporter,
    "ibkr": IBKRFlexImporter,
}


CRYPTO_ASSETS_BY_SYMBOL = {row["symbol"]: row for row in CRYPTO_ASSETS}
ETF_ASSETS_BY_SYMBOL = {row["symbol"]: row for row in ETF_ASSETS}
_SAFE_TICKER = re.compile(r"^[A-Z0-9.-]{1,15}$")


def get_importer(broker_key: str):
    importer_cls = IMPORTERS.get(broker_key)
    if importer_cls is None:
        raise ValueError(f"Unknown broker import source: {broker_key!r}")
    return importer_cls()


def resolve_asset_id(symbol: str):
    """Match a broker's raw symbol against the curated Fase 1 universe.

    Tries yahoo_symbol first (already broker-suffix-agnostic for most
    Canadian tickers, e.g. 'RY.TO'), then the bare `symbol` column. Returns
    None if unmatched -- the caller marks the row 'unknown_symbol' rather
    than auto-creating an Asset, since that catalog is curated separately.
    """
    symbol = symbol.strip().upper()
    asset = Asset.query.filter_by(yahoo_symbol=symbol).first()
    if asset is None:
        asset = Asset.query.filter_by(symbol=symbol).first()
    return asset.id if asset else None


def _create_catalog_asset(row: dict) -> int:
    asset = Asset(**row)
    db.session.add(asset)
    db.session.flush()
    return asset.id


def _discover_asset(normalized: str, currency_hint: str | None) -> int | None:
    if (
        not has_app_context()
        or not current_app.config.get("DISCOVER_UNKNOWN_ASSETS_ON_ORDER_CREATE", True)
        or not _SAFE_TICKER.fullmatch(normalized)
    ):
        return None

    # Explicit Yahoo/Canadian suffixes are respected. For a bare ticker, the
    # order currency gives the best first guess and avoids an unnecessary
    # failed request for the overwhelmingly common case.
    yahoo_base = normalized.replace(".", "-")
    if normalized.endswith(".TO"):
        candidates = [normalized]
    elif (currency_hint or "").upper() == "USD":
        candidates = [yahoo_base, f"{yahoo_base}.TO"]
    else:
        candidates = [f"{yahoo_base}.TO", yahoo_base]

    from src.services.market_data import get_provider

    provider = get_provider(max_retries=1, min_interval_seconds=0)
    for candidate in candidates:
        metadata = provider.get_asset_metadata(candidate)
        if metadata is None:
            continue
        existing = Asset.query.filter_by(
            symbol=metadata["symbol"], exchange=metadata["exchange"]
        ).first()
        return existing.id if existing else _create_catalog_asset(metadata)
    return None


def resolve_or_create_manual_asset(symbol: str, currency_hint: str | None = None):
    """Resolve a curated asset or validate and create an exact ticker.

    Crypto and popular ETFs come from the built-in catalog. Other exact stock
    or ETF tickers are accepted only when Yahoo confirms a live CAD/USD quote
    on a supported North American exchange.
    """
    normalized = symbol.strip().upper()
    crypto_symbol = normalized.removesuffix("-CAD").removesuffix("-USD")

    catalog_row = CRYPTO_ASSETS_BY_SYMBOL.get(crypto_symbol)
    if catalog_row is not None:
        # A stock universe may legitimately contain the same bare ticker, and
        # typing BTC must not bind the order to that unrelated security.
        asset = Asset.query.filter_by(symbol=crypto_symbol, exchange="CRYPTO").first()
        if asset is None:
            asset = Asset.query.filter_by(yahoo_symbol=catalog_row["yahoo_symbol"]).first()
        return asset.id if asset else _create_catalog_asset(catalog_row)

    existing_id = resolve_asset_id(normalized)
    if existing_id is not None:
        return existing_id

    etf_symbol = normalized.removesuffix(".TO")
    catalog_row = ETF_ASSETS_BY_SYMBOL.get(etf_symbol)
    if catalog_row is not None:
        asset = Asset.query.filter_by(
            symbol=catalog_row["symbol"], exchange=catalog_row["exchange"]
        ).first()
        return asset.id if asset else _create_catalog_asset(catalog_row)

    return _discover_asset(normalized, currency_hint)
