import io
from datetime import datetime

from src.models import Asset
from src.resources.orders_import.ibkr import IBKRFlexImporter
from src.resources.orders_import.questrade import QuestradeCSVImporter
from src.resources.orders_import.registry import resolve_asset_id
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
