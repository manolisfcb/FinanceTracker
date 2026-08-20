from datetime import date, datetime

from src.models import Account, AccountType, Asset, DividendHistory, DividendReceived, Fundamentals, FxRate, OrderModel, OrderType
from src.services.portfolio import PortfolioService


def _asset(db, symbol='RY', currency='CAD'):
    asset = Asset(symbol=symbol, yahoo_symbol=f'{symbol}.TO', exchange='TSX', currency=currency, name=symbol)
    db.session.add(asset)
    db.session.commit()
    return asset


def _account(db, user, name='Margin', type_=AccountType.MARGIN):
    account = Account(user_id=user.id, type=type_, name=name)
    db.session.add(account)
    db.session.commit()
    return account


def _order(user, asset, account, type_, quantity, price, fees=0.0, currency='CAD', fx_rate=1.0, when=None):
    return OrderModel(
        user_id=user.id, asset_id=asset.id, account_id=account.id, type=type_,
        quantity=quantity, price=price, fees=fees, currency=currency, fx_rate_to_cad=fx_rate,
        executed_at=when or datetime(2026, 1, 1),
    )


def test_average_cost_unaffected_by_sell(db, user):
    asset = _asset(db)
    account = _account(db, user)
    db.session.add_all([
        _order(user, asset, account, OrderType.BUY, 10, 100.0, when=datetime(2026, 1, 1)),
        _order(user, asset, account, OrderType.BUY, 10, 120.0, when=datetime(2026, 1, 2)),
        _order(user, asset, account, OrderType.SELL, 5, 150.0, when=datetime(2026, 1, 3)),
    ])
    db.session.commit()

    lots = PortfolioService(user.id).compute_lots()
    assert len(lots) == 1
    lot = lots[0]

    assert lot.avg_cost_original == 110.0
    assert lot.quantity == 15
    assert lot.realized_pnl_original == 5 * (150.0 - 110.0)


def test_nonregistered_accounts_pool_together(db, user):
    asset = _asset(db)
    margin = _account(db, user, name='Margin', type_=AccountType.MARGIN)
    cash = _account(db, user, name='Cash', type_=AccountType.CASH)
    db.session.add_all([
        _order(user, asset, margin, OrderType.BUY, 10, 100.0),
        _order(user, asset, cash, OrderType.BUY, 5, 200.0),
    ])
    db.session.commit()

    lots = PortfolioService(user.id).compute_lots()
    assert len(lots) == 1
    lot = lots[0]
    assert lot.quantity == 15
    assert lot.quantity_by_account[margin.id] == 10
    assert lot.quantity_by_account[cash.id] == 5


def test_registered_accounts_are_isolated_pools(db, user):
    asset = _asset(db)
    tfsa = _account(db, user, name='TFSA', type_=AccountType.TFSA)
    margin = _account(db, user, name='Margin', type_=AccountType.MARGIN)
    db.session.add_all([
        _order(user, asset, tfsa, OrderType.BUY, 10, 100.0),
        _order(user, asset, margin, OrderType.BUY, 10, 200.0),
    ])
    db.session.commit()

    lots = PortfolioService(user.id).compute_lots()
    assert len(lots) == 2
    avg_costs = sorted(lot.avg_cost_original for lot in lots)
    assert avg_costs == [100.0, 200.0]


def test_cad_cost_uses_trade_fx_value_uses_todays_fx(db, user):
    asset = _asset(db, symbol='AAPL', currency='USD')
    account = _account(db, user)
    db.session.add(_order(user, asset, account, OrderType.BUY, 10, 100.0, currency='USD', fx_rate=1.30))
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 19), price=110.0))
    db.session.add(FxRate(date=date(2026, 8, 20), pair='USDCAD', rate=1.35))
    db.session.commit()

    lot = PortfolioService(user.id).compute_lots()[0]

    assert lot.avg_cost_cad == 100.0 * 1.30
    assert lot.market_value_cad == 10 * 110.0 * 1.35


def test_missing_fx_rate_excludes_lot_from_cad_totals(db, user):
    asset = _asset(db, symbol='AAPL', currency='USD')
    account = _account(db, user)
    db.session.add(_order(user, asset, account, OrderType.BUY, 10, 100.0, currency='USD', fx_rate=1.30))
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 19), price=110.0))
    db.session.commit()

    service = PortfolioService(user.id)
    lot = service.compute_lots()[0]

    assert lot.market_value_cad is None
    assert any('FxRate' in w for w in service.warnings)
    assert service.get_totals()['patrimony_cad'] == 0.0


def test_oversell_warns_without_crashing(db, user):
    asset = _asset(db)
    account = _account(db, user)
    db.session.add_all([
        _order(user, asset, account, OrderType.BUY, 5, 100.0, when=datetime(2026, 1, 1)),
        _order(user, asset, account, OrderType.SELL, 10, 120.0, when=datetime(2026, 1, 2)),
    ])
    db.session.commit()

    service = PortfolioService(user.id)
    lot = service.compute_lots()[0]

    assert lot.quantity == -5
    assert any('sold' in w for w in service.warnings)


def test_quantity_held_as_of_respects_cutoff(db, user):
    asset = _asset(db)
    account = _account(db, user)
    db.session.add_all([
        _order(user, asset, account, OrderType.BUY, 10, 100.0, when=datetime(2026, 1, 1)),
        _order(user, asset, account, OrderType.BUY, 5, 100.0, when=datetime(2026, 2, 1)),
    ])
    db.session.commit()

    service = PortfolioService(user.id)
    assert service.quantity_held_as_of(asset.id, date(2026, 1, 15)) == 10
    assert service.quantity_held_as_of(asset.id, date(2026, 2, 15)) == 15


def test_sync_suggested_dividends_creates_unconfirmed_row(db, user):
    asset = _asset(db)
    account = _account(db, user)
    db.session.add(_order(user, asset, account, OrderType.BUY, 10, 100.0, when=datetime(2026, 1, 1)))
    db.session.add(DividendHistory(asset_id=asset.id, ex_date=date(2026, 2, 1), amount=0.5, currency='CAD'))
    db.session.commit()

    created = PortfolioService(user.id).sync_suggested_dividends()
    assert created == 1

    row = DividendReceived.query.filter_by(user_id=user.id, asset_id=asset.id).first()
    assert row.confirmed is False
    assert row.quantity_held == 10
    assert row.total_amount == 5.0


def test_sync_suggested_dividends_skips_when_no_shares_held(db, user):
    asset = _asset(db)
    account = _account(db, user)
    db.session.add(_order(user, asset, account, OrderType.BUY, 10, 100.0, when=datetime(2026, 3, 1)))
    db.session.add(DividendHistory(asset_id=asset.id, ex_date=date(2026, 2, 1), amount=0.5, currency='CAD'))
    db.session.commit()

    created = PortfolioService(user.id).sync_suggested_dividends()
    assert created == 0
    assert DividendReceived.query.count() == 0


def test_sync_suggested_dividends_does_not_overwrite_confirmed(db, user):
    asset = _asset(db)
    account = _account(db, user)
    db.session.add(_order(user, asset, account, OrderType.BUY, 10, 100.0, when=datetime(2026, 1, 1)))
    db.session.add(DividendHistory(asset_id=asset.id, ex_date=date(2026, 2, 1), amount=0.5, currency='CAD'))
    db.session.commit()

    PortfolioService(user.id).sync_suggested_dividends()
    row = DividendReceived.query.filter_by(user_id=user.id, asset_id=asset.id).first()
    row.confirmed = True
    row.total_amount = 999.0
    db.session.commit()

    PortfolioService(user.id).sync_suggested_dividends()
    row = DividendReceived.query.filter_by(user_id=user.id, asset_id=asset.id).first()
    assert row.total_amount == 999.0
