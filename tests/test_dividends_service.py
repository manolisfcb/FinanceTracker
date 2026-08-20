from datetime import date, datetime, timedelta

from src.models import (
    Account,
    AccountType,
    Asset,
    CompanyEvent,
    CompanyEventKind,
    DividendHistory,
    DividendReceived,
    Fundamentals,
    FxRate,
    OrderModel,
    OrderType,
)
from src.services.dividends import DividendsService, _infer_frequency
from src.services.portfolio import PortfolioService


def _asset(db, symbol='RY', currency='CAD', exchange='TSX'):
    asset = Asset(
        symbol=symbol, yahoo_symbol=f'{symbol}.TO', exchange=exchange,
        currency=currency, name=f'{symbol} Inc.',
    )
    db.session.add(asset)
    db.session.commit()
    return asset


def _account(db, user):
    account = Account(user_id=user.id, type=AccountType.MARGIN, name='Margin')
    db.session.add(account)
    db.session.commit()
    return account


def _order(db, user, asset, account, quantity=100, price=50.0, when=None, currency='CAD', fx_rate=1.0):
    db.session.add(OrderModel(
        user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
        quantity=quantity, price=price, fees=0.0, currency=currency, fx_rate_to_cad=fx_rate,
        executed_at=when or datetime(2026, 1, 1),
    ))
    db.session.commit()


def _received(db, user, asset, pay_date, amount, currency='CAD', confirmed=True, dismissed=False):
    row = DividendReceived(
        user_id=user.id, asset_id=asset.id, pay_date=pay_date, quantity_held=100,
        total_amount=amount, currency=currency, confirmed=confirmed, dismissed=dismissed,
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_monthly_received_buckets_by_pay_month_and_zero_fills(db, user):
    asset = _asset(db)
    today = date(2026, 8, 20)
    _received(db, user, asset, date(2026, 8, 5), 100.0)
    _received(db, user, asset, date(2026, 8, 25), 50.0)
    _received(db, user, asset, date(2026, 6, 10), 30.0)

    series = DividendsService(user.id).monthly_received(months=12, today=today)

    assert len(series) == 12
    assert series[-1] == {"month": date(2026, 8, 1), "total_cad": 150.0}
    assert series[-3] == {"month": date(2026, 6, 1), "total_cad": 30.0}
    assert series[-2]["total_cad"] == 0.0


def test_monthly_received_converts_foreign_currency_and_skips_dismissed(db, user):
    asset = _asset(db, symbol='AAPL', currency='USD', exchange='US')
    db.session.add(FxRate(date=date(2026, 8, 20), pair='USDCAD', rate=1.4))
    db.session.commit()
    _received(db, user, asset, date(2026, 8, 5), 100.0, currency='USD')
    _received(db, user, asset, date(2026, 8, 6), 999.0, currency='USD', dismissed=True)

    series = DividendsService(user.id).monthly_received(months=3, today=date(2026, 8, 20))

    assert series[-1]["total_cad"] == 140.0


def test_yield_on_cost_uses_dividend_rate_over_average_cost(db, user):
    asset = _asset(db)
    account = _account(db, user)
    _order(db, user, asset, account, quantity=100, price=50.0)
    db.session.add(Fundamentals(
        asset_id=asset.id, as_of_date=date(2026, 8, 20), price=60.0,
        dividend_rate=4.0, dividend_yield=0.0666,
    ))
    db.session.commit()

    rows = DividendsService(user.id).by_position(today=date(2026, 8, 20))

    assert len(rows) == 1
    assert rows[0]["yoc"] == 4.0 / 50.0
    assert rows[0]["current_yield"] == 0.0666


def test_yield_on_cost_is_none_without_fundamentals(db, user):
    asset = _asset(db)
    account = _account(db, user)
    _order(db, user, asset, account)

    rows = DividendsService(user.id).by_position(today=date(2026, 8, 20))

    assert rows[0]["yoc"] is None
    assert rows[0]["current_yield"] is None


def test_income_share_splits_across_positions(db, user):
    first = _asset(db, symbol='RY')
    second = _asset(db, symbol='BCE')
    today = date(2026, 8, 20)
    _received(db, user, first, today - timedelta(days=10), 300.0)
    _received(db, user, second, today - timedelta(days=10), 100.0)

    rows = {r["symbol"]: r for r in DividendsService(user.id).by_position(today=today)}

    assert rows["RY"]["income_share_percent"] == 75.0
    assert rows["BCE"]["income_share_percent"] == 25.0


def test_projection_uses_dividend_rate_times_quantity_in_cad(db, user):
    asset = _asset(db, symbol='AAPL', currency='USD', exchange='US')
    account = _account(db, user)
    _order(db, user, asset, account, quantity=10, price=100.0, currency='USD', fx_rate=1.3)
    db.session.add_all([
        FxRate(date=date(2026, 8, 20), pair='USDCAD', rate=1.4),
        Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 20), price=200.0, dividend_rate=2.0),
    ])
    db.session.commit()

    assert DividendsService(user.id).projection_12m() == 10 * 2.0 * 1.4


def test_upcoming_calendar_only_lists_future_events_for_held_assets(db, user):
    held = _asset(db, symbol='ENB')
    not_held = _asset(db, symbol='SU')
    account = _account(db, user)
    _order(db, user, held, account, quantity=120, price=50.0)
    today = date(2026, 8, 20)

    db.session.add_all([
        DividendHistory(asset_id=held.id, ex_date=date(2026, 5, 28), amount=0.9425, currency='CAD'),
        CompanyEvent(
            asset_id=held.id, kind=CompanyEventKind.DIVIDEND, source='YAHOO',
            external_id=f'dividend-next:{held.id}', title='ENB', published_at=datetime.utcnow(),
            event_date=date(2026, 8, 28),
        ),
        CompanyEvent(
            asset_id=held.id, kind=CompanyEventKind.DIVIDEND, source='YAHOO',
            external_id='old', title='ENB pasado', published_at=datetime.utcnow(),
            event_date=date(2026, 1, 1),
        ),
        CompanyEvent(
            asset_id=not_held.id, kind=CompanyEventKind.DIVIDEND, source='YAHOO',
            external_id=f'dividend-next:{not_held.id}', title='SU', published_at=datetime.utcnow(),
            event_date=date(2026, 8, 30),
        ),
    ])
    db.session.commit()

    entries = DividendsService(user.id).upcoming_calendar(today=today)

    assert len(entries) == 1
    assert entries[0]["symbol"] == 'ENB'
    assert entries[0]["estimated_cad"] == 120 * 0.9425


def test_kpis_compare_last_12m_against_previous_period(db, user):
    asset = _asset(db)
    today = date(2026, 8, 20)
    _received(db, user, asset, today - timedelta(days=100), 120.0)
    _received(db, user, asset, today - timedelta(days=500), 100.0)

    kpis = DividendsService(user.id).kpis(today=today)

    assert kpis["received_12m_cad"] == 120.0
    assert kpis["change_vs_previous_percent"] == 20.0
    assert kpis["monthly_average_cad"] == 10.0


def test_pending_suggestions_excludes_confirmed_and_dismissed(db, user):
    asset = _asset(db)
    _received(db, user, asset, date(2026, 8, 1), 10.0, confirmed=False)
    _received(db, user, asset, date(2026, 7, 1), 10.0, confirmed=True)
    _received(db, user, asset, date(2026, 6, 1), 10.0, confirmed=False, dismissed=True)

    suggestions = DividendsService(user.id).pending_suggestions()

    assert [s["pay_date"] for s in suggestions] == [date(2026, 8, 1)]


def test_sync_skips_dismissed_suggestions(db, user):
    asset = _asset(db)
    account = _account(db, user)
    _order(db, user, asset, account, quantity=100, when=datetime(2026, 1, 1))
    db.session.add(DividendHistory(
        asset_id=asset.id, ex_date=date(2026, 3, 1), pay_date=date(2026, 3, 15),
        amount=1.0, currency='CAD',
    ))
    db.session.commit()

    service = PortfolioService(user.id)
    service.sync_suggested_dividends()
    db.session.commit()

    row = DividendReceived.query.filter_by(user_id=user.id).one()
    row.dismissed = True
    row.total_amount = 0.0
    db.session.commit()

    PortfolioService(user.id).sync_suggested_dividends()
    db.session.commit()

    assert DividendReceived.query.filter_by(user_id=user.id).one().total_amount == 0.0


def test_infer_frequency_from_ex_date_cadence():
    quarterly = [date(2026, 1, 1), date(2026, 4, 1), date(2026, 7, 1), date(2026, 10, 1)]
    monthly = [date(2026, m, 1) for m in range(1, 7)]

    assert _infer_frequency(quarterly) == 'Trimestral'
    assert _infer_frequency(monthly) == 'Mensual'
    assert _infer_frequency([date(2026, 1, 1)]) is None
