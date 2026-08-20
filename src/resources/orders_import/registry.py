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


# Yahoo publishes these pairs directly in CAD. Keeping the catalog explicit
# prevents a typo in the manual form from silently creating a bogus asset,
# while covering the cryptoassets commonly held at Canadian brokers.
CRYPTO_ASSETS = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "AVAX": "Avalanche",
    "LINK": "Chainlink",
    "LTC": "Litecoin",
    "BCH": "Bitcoin Cash",
}


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


def resolve_or_create_manual_asset(symbol: str):
    """Resolve a curated asset, creating a supported cryptoasset if needed.

    The broad stock universe remains curated by the seeding job. Crypto is a
    small explicit catalog because users commonly enter ``BTC`` while Yahoo's
    quote symbol is ``BTC-CAD``.
    """
    normalized = symbol.strip().upper()
    crypto_symbol = normalized.removesuffix("-CAD").removesuffix("-USD")

    name = CRYPTO_ASSETS.get(crypto_symbol)
    if name is None:
        return resolve_asset_id(normalized)

    # Prefer the explicit CRYPTO listing. A stock universe may legitimately
    # contain the same bare ticker, and typing BTC must not bind the order to
    # that unrelated security.
    asset = Asset.query.filter_by(symbol=crypto_symbol, exchange="CRYPTO").first()
    if asset is None:
        asset = Asset.query.filter_by(yahoo_symbol=f"{crypto_symbol}-CAD").first()
    if asset is not None:
        return asset.id

    asset = Asset(
        symbol=crypto_symbol,
        yahoo_symbol=f"{crypto_symbol}-CAD",
        exchange="CRYPTO",
        currency="CAD",
        name=name,
        sector="Cryptoassets",
        country="Global",
    )
    db.session.add(asset)
    db.session.flush()
    return asset.id
