from datetime import date, datetime, time, timedelta

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
    PortfolioSnapshotModel,
)
from src.services.dashboard import DONUT_CIRCUMFERENCE, DashboardService

TODAY = date(2026, 8, 20)


def _account(db, user, kind=AccountType.TFSA, name='TFSA'):
    account = Account(user_id=user.id, type=kind, name=name)
    db.session.add(account)
    db.session.commit()
    return account


def _asset(db, symbol='RY', sector='Financial Services', currency='CAD', exchange='TSX'):
    asset = Asset(symbol=symbol, yahoo_symbol=symbol, exchange=exchange, currency=currency,
                  name=f'{symbol} Inc', sector=sector)
    db.session.add(asset)
    db.session.commit()
    return asset


def _buy(db, user, account, asset, quantity=10, price=100.0, when=datetime(2026, 8, 5),
         fx_rate=1.0):
    db.session.add(OrderModel(
        user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
        quantity=quantity, price=price, fees=0.0, currency=asset.currency,
        fx_rate_to_cad=fx_rate, executed_at=when,
    ))
    db.session.commit()


def _price(db, asset, price):
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=TODAY, price=price))
    db.session.commit()


def _service(user):
    return DashboardService(user.id, today=TODAY)


# -- KPI band ---------------------------------------------------------------

def test_kpis_report_value_cost_and_gain(app, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset, quantity=10, price=100.0)
    _price(db, asset, 120.0)

    kpis = _service(user).kpis()

    assert kpis['patrimony_cad'] == 1200.0
    assert kpis['invested_cad'] == 1000.0
    assert kpis['gain_cad'] == 200.0
    assert kpis['gain_percent'] == 20.0


def test_day_change_compares_the_last_two_snapshots(app, db, user):
    for day, patrimony in ((TODAY - timedelta(days=1), 1000.0), (TODAY, 1100.0)):
        db.session.add(PortfolioSnapshotModel(
            user_id=user.id, account_id=None, date=day, patrimony_cad=patrimony,
            total_invested_cad=900.0, dividends_accum_cad=0.0,
        ))
    db.session.commit()

    kpis = _service(user).kpis()

    assert kpis['change_percent'] == 10.0
    assert kpis['change_is_today'] is True


def test_day_change_is_none_with_a_single_snapshot(app, db, user):
    db.session.add(PortfolioSnapshotModel(
        user_id=user.id, account_id=None, date=TODAY, patrimony_cad=1000.0,
        total_invested_cad=900.0, dividends_accum_cad=0.0,
    ))
    db.session.commit()

    assert _service(user).kpis()['change_percent'] is None


def test_yield_on_cost_measures_the_forward_payout_against_cost(app, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset, quantity=100, price=10.0)  # 1000 of cost
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=TODAY, price=12.0, dividend_rate=0.4))
    db.session.commit()

    kpis = _service(user).kpis()

    # 100 shares x C$0.40 a year = C$40 against C$1000 of cost.
    assert kpis['projection_12m_cad'] == 40.0
    assert kpis['yield_on_cost_percent'] == 4.0


# -- allocation -------------------------------------------------------------

def test_sector_allocation_weights_by_market_value(app, db, user):
    account = _account(db, user)
    banks = _asset(db, 'RY', 'Financial Services')
    energy = _asset(db, 'ENB', 'Energy')
    _buy(db, user, account, banks, quantity=10, price=100.0)
    _buy(db, user, account, energy, quantity=10, price=100.0)
    _price(db, banks, 150.0)
    _price(db, energy, 50.0)

    slices = _service(user).sector_allocation()

    assert [(s['label'], s['percent']) for s in slices] == [
        ('Financial Services', 75.0),
        ('Energy', 25.0),
    ]
    # The slices are dash segments on one circle, so they have to tile it
    # (each dash is rounded to two decimals, hence the tolerance).
    assert abs(sum(s['dash'] for s in slices) - DONUT_CIRCUMFERENCE) < 0.05
    assert slices[0]['offset'] == 0.0
    assert slices[1]['offset'] == -slices[0]['dash']


def test_sectors_past_the_fifth_are_pooled_into_otros(app, db, user):
    account = _account(db, user)
    for index in range(7):
        asset = _asset(db, f'A{index}', f'Sector {index}')
        _buy(db, user, account, asset, quantity=10, price=10.0)
        _price(db, asset, 10.0 * (7 - index))

    slices = _service(user).sector_allocation()

    assert len(slices) == 6
    assert slices[-1]['label'] == 'Otros'


def test_currency_allocation_splits_by_the_currency_traded_in(app, db, user):
    account = _account(db, user)
    cad_asset = _asset(db, 'RY', 'Financial Services', currency='CAD')
    usd_asset = _asset(db, 'MSFT', 'Technology', currency='USD', exchange='NASDAQ')
    _buy(db, user, account, cad_asset, quantity=10, price=100.0)
    _buy(db, user, account, usd_asset, quantity=10, price=100.0, fx_rate=1.0)
    _price(db, cad_asset, 150.0)
    _price(db, usd_asset, 50.0)
    db.session.add(FxRate(date=TODAY, pair='USDCAD', rate=1.0))
    db.session.commit()

    rows = _service(user).currency_allocation()

    assert [(r['currency'], r['percent']) for r in rows] == [('CAD', 75.0), ('USD', 25.0)]


# -- contributions ----------------------------------------------------------

def test_monthly_contributions_scale_bars_against_the_biggest_month(app, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset, quantity=10, price=100.0, when=datetime(2026, 7, 10))
    _buy(db, user, account, asset, quantity=5, price=100.0, when=datetime(2026, 8, 3))

    contributions = _service(user).monthly_contributions()

    assert len(contributions['bars']) == 12
    july, august = contributions['bars'][-2], contributions['bars'][-1]
    assert july['total_cad'] == 1000.0
    assert august['total_cad'] == 500.0
    assert july['height'] > august['height']
    # The current month is the highlighted bar and the one the footer quotes.
    assert august['is_current'] is True
    assert contributions['current'] is august


def test_contributions_convert_foreign_orders_at_their_own_trade_rate(app, db, user):
    account = _account(db, user)
    asset = _asset(db, 'MSFT', 'Technology', currency='USD', exchange='NASDAQ')
    _buy(db, user, account, asset, quantity=10, price=100.0, when=datetime(2026, 8, 3), fx_rate=1.4)

    bars = _service(user).monthly_contributions()['bars']

    assert bars[-1]['total_cad'] == 1400.0


def test_contributions_are_flat_when_nothing_was_bought_in_the_window(app, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset, when=datetime(2020, 1, 5))

    contributions = _service(user).monthly_contributions()

    assert contributions['total_cad'] == 0.0
    assert all(bar['height'] == 0 for bar in contributions['bars'])


# -- top positions ----------------------------------------------------------

def test_top_positions_are_the_five_biggest_by_market_value(app, db, user):
    account = _account(db, user)
    for index in range(7):
        asset = _asset(db, f'A{index}')
        _buy(db, user, account, asset, quantity=10, price=10.0)
        _price(db, asset, 10.0 * (index + 1))

    rows = _service(user).top_positions()

    assert [row['symbol'] for row in rows] == ['A6', 'A5', 'A4', 'A3', 'A2']


# -- upcoming events --------------------------------------------------------

def _event(db, asset, kind, title, published_at, event_date=None, external_id=None):
    event = CompanyEvent(
        asset_id=asset.id, kind=kind, source='test', external_id=external_id or title,
        title=title, published_at=published_at, event_date=event_date,
    )
    db.session.add(event)
    db.session.commit()
    return event


def test_upcoming_events_estimate_what_a_dividend_will_pay(app, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset, quantity=100, price=10.0)
    _price(db, asset, 10.0)
    db.session.add(DividendHistory(asset_id=asset.id, ex_date=date(2026, 5, 28),
                                   pay_date=date(2026, 6, 15), amount=0.9425, currency='CAD'))
    db.session.commit()
    _event(db, asset, CompanyEventKind.DIVIDEND, 'RY — ex-dividend',
           datetime(2026, 8, 1), event_date=date(2026, 8, 28))

    events = _service(user).upcoming_events()

    assert len(events) == 1
    assert events[0]['symbol'] == 'RY'
    assert events[0]['amount_per_share'] == 0.9425
    assert round(events[0]['estimated_cad'], 2) == 94.25
    assert events[0]['is_upcoming'] is True


def test_upcoming_events_come_first_and_news_never_backfills(app, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset)
    _price(db, asset, 100.0)
    _event(db, asset, CompanyEventKind.EARNINGS, 'RY — resultados',
           datetime(2026, 8, 1), event_date=date(2026, 8, 27))
    _event(db, asset, CompanyEventKind.FILING, 'RY — 8-K', datetime(2026, 8, 18))
    _event(db, asset, CompanyEventKind.NEWS, 'RY sube en la apertura', datetime(2026, 8, 19))

    events = _service(user).upcoming_events()

    assert [e['title'] for e in events] == ['RY — resultados', 'RY — 8-K']


def test_events_of_assets_that_are_not_held_are_left_out(app, db, user):
    account = _account(db, user)
    held = _asset(db, 'RY')
    other = _asset(db, 'SU', 'Energy')
    _buy(db, user, account, held)
    _price(db, held, 100.0)
    _event(db, other, CompanyEventKind.EARNINGS, 'SU — resultados',
           datetime(2026, 8, 1), event_date=date(2026, 8, 25))

    assert _service(user).upcoming_events() == []


# -- market status ----------------------------------------------------------

def test_market_status_follows_the_toronto_session(app, db, user):
    from src.services.dashboard import MARKET_TZ

    service = _service(user)
    wednesday_noon = datetime.combine(date(2026, 8, 19), time(12, 0), tzinfo=MARKET_TZ)
    wednesday_night = datetime.combine(date(2026, 8, 19), time(20, 0), tzinfo=MARKET_TZ)
    saturday_noon = datetime.combine(date(2026, 8, 22), time(12, 0), tzinfo=MARKET_TZ)

    assert service.market_status(wednesday_noon)['open'] is True
    assert service.market_status(wednesday_night)['open'] is False
    assert service.market_status(saturday_noon)['open'] is False


# -- the page ---------------------------------------------------------------

def test_dashboard_renders_every_card_with_real_numbers(auth_client, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset, quantity=10, price=100.0, when=datetime(2026, 8, 5))
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date.today(), price=120.0))
    db.session.add(DividendReceived(
        user_id=user.id, asset_id=asset.id, pay_date=date.today() - timedelta(days=30),
        quantity_held=10, total_amount=25.0, currency='CAD', confirmed=True,
    ))
    db.session.commit()

    body = auth_client.get('/dashboard').get_data(as_text=True)

    assert 'Evolución del patrimonio' in body
    assert 'Alocación por sector' in body
    assert 'Aportes mensuales' in body
    assert 'Top posiciones' in body
    assert 'Próximos eventos' in body
    assert 'C$1,200.00' in body       # patrimonio
    assert '+C$200.00' in body        # ganancia total
    assert 'Financial Services' in body
    assert 'C$25.00' in body          # dividendos 12m


def test_dashboard_empty_state_does_not_blow_up(auth_client, db, user):
    body = auth_client.get('/dashboard').get_data(as_text=True)

    assert 'Todavía no hay snapshots diarios' in body
    assert 'Todavía no tienes posiciones abiertas.' in body
    assert 'Sin eventos anunciados' in body


def test_recalculate_writes_todays_snapshot(auth_client, db, user):
    account = _account(db, user)
    asset = _asset(db)
    _buy(db, user, account, asset, quantity=10, price=100.0)
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date.today(), price=110.0))
    db.session.commit()

    response = auth_client.post('/dashboard/recalculate')

    assert response.status_code == 302
    snapshot = PortfolioSnapshotModel.query.filter_by(
        user_id=user.id, account_id=None, date=date.today()
    ).one()
    assert snapshot.patrimony_cad == 1100.0
