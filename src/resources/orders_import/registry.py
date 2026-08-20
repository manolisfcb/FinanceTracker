from src.models import Asset
from src.resources.orders_import.ibkr import IBKRFlexImporter
from src.resources.orders_import.questrade import QuestradeCSVImporter
from src.resources.orders_import.wealthsimple import WealthsimpleCSVImporter

IMPORTERS = {
    "questrade": QuestradeCSVImporter,
    "wealthsimple": WealthsimpleCSVImporter,
    "ibkr": IBKRFlexImporter,
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
