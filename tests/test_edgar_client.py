from unittest.mock import MagicMock, patch

import pytest

from src.services import edgar

# No network: SEC responses are mocked at the point of use.


@pytest.fixture(autouse=True)
def _clear_ticker_map_cache():
    edgar._ticker_map_cache = None
    yield
    edgar._ticker_map_cache = None


def _response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


TICKERS_PAYLOAD = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}

SUBMISSIONS_PAYLOAD = {
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "accessionNumber": ["0000320193-26-000101", "0000320193-26-000099", "0000320193-26-000098"],
            "form": ["8-K", "S-8", "10-Q"],
            "filingDate": ["2026-08-15", "2026-08-10", "2026-07-30"],
            "reportDate": ["2026-08-15", "", "2026-06-30"],
            "primaryDocument": ["a8k.htm", "s8.htm", "a10q.htm"],
            "primaryDocDescription": ["8-K report", "S-8 registration", "10-Q report"],
        }
    },
}


@patch('src.services.edgar.requests.get')
def test_resolve_cik_zero_pads_to_ten_digits(mock_get, app):
    mock_get.return_value = _response(TICKERS_PAYLOAD)

    with app.app_context():
        assert edgar.resolve_cik('AAPL') == '0000320193'
        assert edgar.resolve_cik('msft') == '0000789019'
        assert edgar.resolve_cik('RY') is None

    assert mock_get.call_count == 1  # ticker map is cached per process


@patch('src.services.edgar.requests.get')
def test_requests_carry_the_configured_user_agent(mock_get, app):
    mock_get.return_value = _response(TICKERS_PAYLOAD)

    with app.app_context():
        edgar.resolve_cik('AAPL')

    headers = mock_get.call_args.kwargs['headers']
    assert headers['User-Agent'] == app.config['SEC_EDGAR_USER_AGENT']


@patch('src.services.edgar.requests.get')
def test_get_recent_filings_filters_forms_and_builds_urls(mock_get, app):
    mock_get.return_value = _response(SUBMISSIONS_PAYLOAD)

    with app.app_context():
        filings = edgar.get_recent_filings('0000320193')

    assert [f['form'] for f in filings] == ['8-K', '10-Q']
    assert filings[0]['accession_number'] == '0000320193-26-000101'
    assert filings[0]['url'] == (
        'https://www.sec.gov/Archives/edgar/data/320193/000032019326000101/a8k.htm'
    )
    assert filings[1]['filing_date'] == '2026-07-30'


@patch('src.services.edgar.requests.get')
def test_get_recent_filings_respects_limit(mock_get, app):
    mock_get.return_value = _response(SUBMISSIONS_PAYLOAD)

    with app.app_context():
        filings = edgar.get_recent_filings('0000320193', limit=1)

    assert len(filings) == 1
