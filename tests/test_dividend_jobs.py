from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.models import (
    Account,
    AccountType,
    Asset,
    CompanyEvent,
    CompanyEventKind,
    DividendHistory,
    OrderModel,
    OrderType,
)
from src.resources.jobs.refresh_company_events import _refresh_company_events
from src.resources.jobs.refresh_dividends import _refresh_held_dividends


def _held_asset(db, user, symbol='RY', exchange='TSX'):
    asset = Asset(
        symbol=symbol, yahoo_symbol=f'{symbol}.TO', exchange=exchange,
        currency='CAD', name=f'{symbol} Inc.',
    )
    db.session.add(asset)
    db.session.commit()

    account = Account.query.filter_by(user_id=user.id).first()
    if account is None:
        account = Account(user_id=user.id, type=AccountType.MARGIN, name='Margin')
        db.session.add(account)
        db.session.commit()

    db.session.add(OrderModel(
        user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
        quantity=10, price=100.0, currency='CAD', executed_at=datetime(2026, 1, 1),
    ))
    db.session.commit()
    return asset


def _provider(dividends=None, calendar=None):
    provider = MagicMock()
    provider.get_dividends.return_value = dividends or []
    provider.get_calendar.return_value = calendar
    return provider


@patch('src.resources.jobs.refresh_dividends.get_provider')
def test_refresh_dividends_only_touches_held_assets(mock_get_provider, app, db, user):
    held = _held_asset(db, user, symbol='RY')
    db.session.add(Asset(
        symbol='SU', yahoo_symbol='SU.TO', exchange='TSX', currency='CAD', name='Suncor',
    ))
    db.session.commit()

    mock_get_provider.return_value = _provider(dividends=[
        {'ex_date': date(2026, 5, 28), 'pay_date': None, 'amount': 1.42, 'currency': 'CAD'},
    ])

    with app.app_context():
        items = _refresh_held_dividends()
        db.session.commit()

    assert items == 1
    rows = DividendHistory.query.all()
    assert len(rows) == 1
    assert rows[0].asset_id == held.id
    assert rows[0].amount == 1.42


@patch('src.resources.jobs.refresh_dividends.get_provider')
def test_refresh_dividends_rerun_updates_instead_of_duplicating(mock_get_provider, app, db, user):
    _held_asset(db, user)
    mock_get_provider.return_value = _provider(dividends=[
        {'ex_date': date(2026, 5, 28), 'pay_date': None, 'amount': 1.42, 'currency': 'CAD'},
    ])

    with app.app_context():
        _refresh_held_dividends()
        db.session.commit()

    mock_get_provider.return_value = _provider(dividends=[
        {'ex_date': date(2026, 5, 28), 'pay_date': date(2026, 6, 15), 'amount': 1.50, 'currency': 'CAD'},
    ])
    with app.app_context():
        _refresh_held_dividends()
        db.session.commit()

    row = DividendHistory.query.one()
    assert row.amount == 1.50
    assert row.pay_date == date(2026, 6, 15)


@patch('src.resources.jobs.refresh_dividends.get_provider')
def test_upcoming_dividend_event_is_a_single_row_per_asset(mock_get_provider, app, db, user):
    asset = _held_asset(db, user)
    future = date.today() + timedelta(days=8)
    mock_get_provider.return_value = _provider(calendar={
        'ex_dividend_date': future, 'dividend_pay_date': None, 'next_earnings_date': None,
    })

    with app.app_context():
        _refresh_held_dividends()
        db.session.commit()

    later = future + timedelta(days=90)
    mock_get_provider.return_value = _provider(calendar={
        'ex_dividend_date': later, 'dividend_pay_date': None, 'next_earnings_date': None,
    })
    with app.app_context():
        _refresh_held_dividends()
        db.session.commit()

    event = CompanyEvent.query.filter_by(kind=CompanyEventKind.DIVIDEND).one()
    assert event.asset_id == asset.id
    assert event.event_date == later


@patch('src.resources.jobs.refresh_dividends.get_provider')
def test_past_ex_date_creates_no_upcoming_event(mock_get_provider, app, db, user):
    _held_asset(db, user)
    mock_get_provider.return_value = _provider(calendar={
        'ex_dividend_date': date.today() - timedelta(days=3),
        'dividend_pay_date': None,
        'next_earnings_date': None,
    })

    with app.app_context():
        _refresh_held_dividends()
        db.session.commit()

    assert CompanyEvent.query.count() == 0


@patch('src.resources.jobs.refresh_company_events.edgar')
@patch('src.resources.jobs.refresh_company_events.get_provider')
def test_filings_are_only_fetched_for_us_assets(mock_get_provider, mock_edgar, app, db, user):
    _held_asset(db, user, symbol='RY', exchange='TSX')
    us_asset = _held_asset(db, user, symbol='AAPL', exchange='US')
    mock_get_provider.return_value = _provider()
    mock_edgar.resolve_cik.return_value = '0000320193'
    mock_edgar.get_recent_filings.return_value = [{
        'form': '8-K',
        'filing_date': date.today().isoformat(),
        'accession_number': '0000320193-26-000101',
        'url': 'https://sec.gov/filing',
    }]

    with app.app_context():
        items = _refresh_company_events()
        db.session.commit()

    assert items == 2
    mock_edgar.resolve_cik.assert_called_once_with('AAPL')
    event = CompanyEvent.query.filter_by(kind=CompanyEventKind.FILING).one()
    assert event.asset_id == us_asset.id
    assert event.source == 'EDGAR'
    assert Asset.query.get(us_asset.id).cik == '0000320193'


@patch('src.resources.jobs.refresh_company_events.edgar')
@patch('src.resources.jobs.refresh_company_events.get_provider')
def test_filings_are_not_duplicated_on_rerun(mock_get_provider, mock_edgar, app, db, user):
    _held_asset(db, user, symbol='AAPL', exchange='US')
    mock_get_provider.return_value = _provider()
    mock_edgar.resolve_cik.return_value = '0000320193'
    mock_edgar.get_recent_filings.return_value = [{
        'form': '8-K',
        'filing_date': date.today().isoformat(),
        'accession_number': '0000320193-26-000101',
        'url': 'https://sec.gov/filing',
    }]

    with app.app_context():
        _refresh_company_events()
        db.session.commit()
        _refresh_company_events()
        db.session.commit()

    assert CompanyEvent.query.filter_by(kind=CompanyEventKind.FILING).count() == 1


@patch('src.resources.jobs.refresh_company_events.edgar')
@patch('src.resources.jobs.refresh_company_events.get_provider')
def test_next_earnings_row_updates_in_place(mock_get_provider, mock_edgar, app, db, user):
    asset = _held_asset(db, user)
    first = date.today() + timedelta(days=20)
    mock_get_provider.return_value = _provider(calendar={'next_earnings_date': first})

    with app.app_context():
        _refresh_company_events()
        db.session.commit()

    moved = first + timedelta(days=2)
    mock_get_provider.return_value = _provider(calendar={'next_earnings_date': moved})
    with app.app_context():
        _refresh_company_events()
        db.session.commit()

    event = CompanyEvent.query.filter_by(kind=CompanyEventKind.EARNINGS).one()
    assert event.asset_id == asset.id
    assert event.event_date == moved
