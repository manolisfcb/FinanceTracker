from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.models import Asset, CompanyEvent, CompanyEventKind, DividendHistory
from src.services import company_data


@pytest.fixture(autouse=True)
def _clear_backfill_cache():
    company_data._backfill_attempts.clear()
    yield
    company_data._backfill_attempts.clear()


def _asset(db, symbol='AAPL', exchange='US'):
    asset = Asset(
        symbol=symbol, yahoo_symbol=symbol, exchange=exchange, currency='USD',
        name='Apple Inc.',
    )
    db.session.add(asset)
    db.session.commit()
    return asset


def _market_provider(dividends=None, calendar=None):
    provider = MagicMock()
    provider.get_dividends.return_value = dividends or []
    provider.get_calendar.return_value = calendar
    provider.get_quote.return_value = None
    return provider


def _news_provider(stories):
    provider = MagicMock()
    provider.name = 'YAHOO'
    provider.get_news.return_value = stories
    return provider


@patch('src.services.company_data.edgar')
@patch('src.services.company_data.get_news_providers')
@patch('src.services.company_data.get_provider')
def test_backfill_fills_every_source_for_one_asset(
    mock_provider, mock_news, mock_edgar, app, db
):
    asset = _asset(db)
    mock_provider.return_value = _market_provider(
        dividends=[{'ex_date': date(2026, 5, 8), 'pay_date': None, 'amount': 0.26, 'currency': 'USD'}],
        calendar={'next_earnings_date': date.today() + timedelta(days=10),
                  'ex_dividend_date': None, 'dividend_pay_date': None},
    )
    mock_edgar.resolve_cik.return_value = '0000320193'
    mock_edgar.get_recent_filings.return_value = [{
        'form': '10-Q', 'filing_date': date.today().isoformat(),
        'accession_number': 'acc-1', 'url': 'https://sec.gov/f',
    }]
    mock_news.return_value = [_news_provider([{
        'title': 'AAPL lanza producto', 'summary': None, 'url': 'https://n/1',
        'published_at': datetime(2026, 8, 19, 12, 0), 'source_name': 'Reuters',
    }])]

    with app.app_context():
        assert company_data.backfill_asset(asset) is True

    assert DividendHistory.query.filter_by(asset_id=asset.id).count() == 1
    kinds = {e.kind for e in CompanyEvent.query.filter_by(asset_id=asset.id).all()}
    assert kinds == {CompanyEventKind.EARNINGS, CompanyEventKind.FILING, CompanyEventKind.NEWS}


@patch('src.services.company_data.edgar')
@patch('src.services.company_data.get_news_providers')
@patch('src.services.company_data.get_provider')
def test_backfill_is_not_retried_within_the_ttl(mock_provider, mock_news, mock_edgar, app, db):
    asset = _asset(db)
    mock_provider.return_value = _market_provider()
    mock_news.return_value = []
    mock_edgar.resolve_cik.return_value = None

    with app.app_context():
        assert company_data.backfill_asset(asset) is True
        assert company_data.backfill_asset(asset) is False

    assert mock_provider.call_count == 1


@patch('src.services.company_data.get_provider')
def test_backfill_failure_leaves_the_asset_empty_without_raising(mock_provider, app, db):
    asset = _asset(db)
    mock_provider.side_effect = Exception('Yahoo is down')

    with app.app_context():
        assert company_data.backfill_asset(asset) is False

    assert CompanyEvent.query.count() == 0


def test_needs_backfill_until_both_dividends_and_news_exist(app, db):
    asset = _asset(db)

    assert company_data.needs_backfill(asset) is True

    db.session.add(DividendHistory(
        asset_id=asset.id, ex_date=date(2026, 5, 8), amount=0.26, currency='USD',
    ))
    db.session.commit()

    assert company_data.needs_backfill(asset) is True

    db.session.add(CompanyEvent(
        asset_id=asset.id, kind=CompanyEventKind.NEWS, source='YAHOO', external_id='n-1',
        title='AAPL en las noticias', published_at=datetime(2026, 8, 19, 12, 0),
    ))
    db.session.commit()

    assert company_data.needs_backfill(asset) is False


def test_a_half_filled_asset_is_still_backfilled(app, db):
    """The bug this guard replaced: an asset with only EDGAR filings (no
    dividends, no news) counted as 'has data' and never got completed."""
    asset = _asset(db)
    db.session.add(CompanyEvent(
        asset_id=asset.id, kind=CompanyEventKind.FILING, source='EDGAR', external_id='acc-1',
        title='AAPL — 10-Q', published_at=datetime(2026, 7, 31, 0, 0),
    ))
    db.session.commit()

    assert company_data.needs_backfill(asset) is True


@patch('src.routes.stockViews.get_provider')
@patch('src.routes.stockViews.backfill_asset')
@patch('src.routes.stockViews.needs_backfill')
def test_company_page_backfills_only_when_data_is_missing(
    mock_needs, mock_backfill, mock_quote_provider, auth_client, db
):
    _asset(db)
    mock_quote_provider.return_value.get_quote.return_value = None
    mock_needs.return_value = True

    assert auth_client.get('/stocks/US/AAPL').status_code == 200
    assert mock_backfill.call_count == 1

    mock_needs.return_value = False
    assert auth_client.get('/stocks/US/AAPL').status_code == 200
    assert mock_backfill.call_count == 1
