import io
from datetime import datetime

from unittest.mock import MagicMock, patch

from src.data.asset_catalog import CRYPTO_ASSETS, ETF_ASSETS, REIT_ASSETS
from src.models import Asset
from src.resources.orders_import.ibkr import IBKRFlexImporter
from src.resources.orders_import.questrade import QuestradeCSVImporter
from src.resources.orders_import.registry import resolve_asset_id, resolve_or_create_manual_asset
from src.resources.orders_import.wealthsimple import WealthsimpleCSVImporter


def _csv(text):
    return io.StringIO(text)


def test_questrade_importer_parses_buy_and_sell():
    csv_text = (
        "Transaction Date,Action,Symbol,Quantity,Price,Commission,Currency\n"
        "2026-01-15,Buy,RY.TO,10,150.25,4.95,CAD\n"
        "2026-01-16,Sell,RY.TO,5,155.00,4.95,CAD\n"
        "2026-01-17,DIV,RY.TO,0,0,0,CAD\n"
    )
    rows = QuestradeCSVImporter().parse(_csv(csv_text))
    assert len(rows) == 2
    assert rows[0].symbol == 'RY.TO'
    assert rows[0].type == 'BUY'
    assert rows[0].quantity == 10
    assert rows[0].price == 150.25
    assert rows[0].fees == 4.95
    assert rows[0].executed_at == datetime(2026, 1, 15)
    assert rows[1].type == 'SELL'


def test_wealthsimple_importer_parses_buy():
    csv_text = (
        "Date,Transaction Type,Symbol,Quantity,Price,Amount,Currency\n"
        "2026-02-01,Buy,AAPL,3,180.00,540.50,USD\n"
    )
    rows = WealthsimpleCSVImporter().parse(_csv(csv_text))
    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == 'AAPL'
    assert row.quantity == 3
    assert row.price == 180.00
    assert row.currency == 'USD'
    assert round(row.fees, 2) == 0.50


def test_ibkr_importer_parses_trade():
    csv_text = (
        "Symbol,TradeDate,Quantity,TradePrice,IBCommission,CurrencyPrimary,Buy/Sell\n"
        "TD,20260301,20,95.5,1.25,CAD,BUY\n"
    )
    rows = IBKRFlexImporter().parse(_csv(csv_text))
    assert len(rows) == 1
    row = rows[0]
    assert row.symbol == 'TD'
    assert row.quantity == 20
    assert row.executed_at == datetime(2026, 3, 1)
    assert row.broker == 'IBKR'


def test_import_hash_is_stable_and_deterministic():
    csv_text = "Transaction Date,Action,Symbol,Quantity,Price,Commission,Currency\n2026-01-15,Buy,RY.TO,10,150.25,4.95,CAD\n"
    row_a = QuestradeCSVImporter().parse(_csv(csv_text))[0]
    row_b = QuestradeCSVImporter().parse(_csv(csv_text))[0]
    assert row_a.import_hash() == row_b.import_hash()


def test_resolve_asset_id_matches_yahoo_symbol_then_symbol(db):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank')
    db.session.add(asset)
    db.session.commit()

    assert resolve_asset_id('RY.TO') == asset.id
    assert resolve_asset_id('ry.to') == asset.id
    assert resolve_asset_id('RY') == asset.id
    assert resolve_asset_id('UNKNOWN') is None


def test_manual_asset_resolver_creates_supported_crypto_in_cad(db):
    asset_id = resolve_or_create_manual_asset('btc')
    asset = db.session.get(Asset, asset_id)

    assert asset.symbol == 'BTC'
    assert asset.yahoo_symbol == 'BTC-CAD'
    assert asset.exchange == 'CRYPTO'
    assert asset.currency == 'CAD'
    assert resolve_or_create_manual_asset('BTC-CAD') == asset_id


def test_manual_asset_resolver_does_not_create_unknown_symbol(db):
    assert resolve_or_create_manual_asset('NOTACOIN') is None
    assert Asset.query.filter_by(symbol='NOTACOIN').first() is None


def test_supplemental_catalog_has_broad_crypto_and_reit_coverage():
    assert len(CRYPTO_ASSETS) >= 35
    assert len(REIT_ASSETS) >= 50
    assert {'BTC', 'ETH', 'SOL', 'XRP', 'SHIB'} <= {row['symbol'] for row in CRYPTO_ASSETS}
    assert {'O', 'PLD', 'REI.UN', 'MRG.UN'} <= {row['symbol'] for row in REIT_ASSETS}


def test_etf_catalog_includes_canadian_and_us_core_funds(db):
    assert len(ETF_ASSETS) >= 60

    vfv_id = resolve_or_create_manual_asset('VFV')
    voo_id = resolve_or_create_manual_asset('VOO')

    vfv = db.session.get(Asset, vfv_id)
    voo = db.session.get(Asset, voo_id)
    assert (vfv.yahoo_symbol, vfv.exchange, vfv.currency) == ('VFV.TO', 'TSX', 'CAD')
    assert (voo.yahoo_symbol, voo.exchange, voo.currency) == ('VOO', 'US', 'USD')


@patch('src.services.market_data.get_provider')
def test_manual_resolver_discovers_a_live_north_american_etf(mock_get_provider, app, db):
    app.config['DISCOVER_UNKNOWN_ASSETS_ON_ORDER_CREATE'] = True
    provider = MagicMock()
    provider.get_asset_metadata.return_value = {
        'symbol': 'NEWETF', 'yahoo_symbol': 'NEWETF.TO', 'exchange': 'TSX',
        'currency': 'CAD', 'name': 'New ETF', 'sector': 'ETFs',
        'industry': 'Exchange-Traded Fund', 'country': 'Canada',
    }
    mock_get_provider.return_value = provider

    asset_id = resolve_or_create_manual_asset('NEWETF', currency_hint='CAD')

    asset = db.session.get(Asset, asset_id)
    assert asset.yahoo_symbol == 'NEWETF.TO'
    provider.get_asset_metadata.assert_called_once_with('NEWETF.TO')
