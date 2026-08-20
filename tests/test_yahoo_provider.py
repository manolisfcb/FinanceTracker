from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.market_data import yahoo as yahoo_module
from src.services.market_data.yahoo import YahooProvider

# Correctness here shouldn't depend on live Yahoo access (this sandbox is
# rate-limited by Yahoo — see .claude/plans — so every yfinance call is mocked).


@pytest.fixture(autouse=True)
def _clear_price_history_cache():
    yahoo_module._price_history_cache.clear()
    yield
    yahoo_module._price_history_cache.clear()


def _provider():
    return YahooProvider(max_retries=1, min_interval_seconds=0)


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_profile_maps_fields(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.get_info.return_value = {
        'longName': 'Royal Bank of Canada',
        'sector': 'Financial Services',
        'industry': 'Banks',
        'country': 'Canada',
        'website': 'https://www.rbc.com',
        'longBusinessSummary': 'Royal Bank of Canada operates as a diversified financial institution.',
    }
    mock_ticker_cls.return_value = mock_ticker

    profile = _provider().get_profile('RY.TO')

    assert profile == {
        'name': 'Royal Bank of Canada',
        'sector': 'Financial Services',
        'industry': 'Banks',
        'country': 'Canada',
        'website': 'https://www.rbc.com',
        'logo_url': 'https://logo.clearbit.com/rbc.com',
        'description': 'Royal Bank of Canada operates as a diversified financial institution.',
    }


@patch('src.services.market_data.yahoo.time.sleep')
@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_profile_returns_none_when_info_unavailable(mock_ticker_cls, mock_sleep):
    mock_ticker = MagicMock()
    mock_ticker.get_info.side_effect = Exception("429 Too Many Requests")
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_profile('RY.TO') is None


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_fundamentals_maps_known_fields_and_leaves_roic_none(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.get_info.return_value = {
        'currentPrice': 145.2,
        'marketCap': 200_000_000_000,
        'trailingPE': 12.5,
        'returnOnEquity': 0.15,
        'debtToEquity': 45.2,
    }
    mock_ticker_cls.return_value = mock_ticker

    data = _provider().get_fundamentals('RY.TO')

    assert data['price'] == 145.2
    assert data['market_cap'] == 200_000_000_000
    assert data['pe'] == 12.5
    assert data['roe'] == 0.15
    assert data['debt_to_equity'] == 45.2
    # Not exposed by yfinance's `info` dict — must stay None, never guessed.
    assert data['roic'] is None


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_fundamentals_normalizes_dividend_yield_to_a_fraction(mock_ticker_cls):
    # yfinance>=1.6's `dividendYield` is percent-scale (1.65 means 1.65%),
    # unlike every other ratio in `info` (roe/margins/payoutRatio are 0-1
    # fractions) — regression test for a real bug where JPM's ~1.65% yield
    # rendered as 165% because this wasn't normalized before the `percent`
    # display filter multiplied it by 100.
    mock_ticker = MagicMock()
    mock_ticker.get_info.return_value = {'dividendYield': 1.65}
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_fundamentals('JPM')['dividend_yield'] == 0.0165


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_fundamentals_dividend_yield_none_when_absent(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.get_info.return_value = {'trailingPE': 12.5}
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_fundamentals('RY.TO')['dividend_yield'] is None


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_profile_and_fundamentals_uses_a_single_get_info_call(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.get_info.return_value = {
        'longName': 'Royal Bank of Canada',
        'sector': 'Financial Services',
        'website': 'https://www.rbc.com',
        'currentPrice': 145.2,
        'trailingPE': 12.5,
    }
    mock_ticker_cls.return_value = mock_ticker

    profile, fundamentals = _provider().get_profile_and_fundamentals('RY.TO')

    assert profile['name'] == 'Royal Bank of Canada'
    assert fundamentals['price'] == 145.2
    assert fundamentals['pe'] == 12.5
    mock_ticker.get_info.assert_called_once()


@patch('src.services.market_data.yahoo.time.sleep')
@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_profile_and_fundamentals_returns_none_pair_when_info_unavailable(mock_ticker_cls, mock_sleep):
    mock_ticker = MagicMock()
    mock_ticker.get_info.side_effect = Exception("429 Too Many Requests")
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_profile_and_fundamentals('RY.TO') == (None, None)


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_quote_maps_fast_info(mock_ticker_cls):
    mock_ticker = MagicMock()
    # yfinance>=1.0's FastInfo keys are camelCase (lastPrice/previousClose) —
    # differs from 0.2.x's snake_case; this test pins the real current shape.
    mock_ticker.fast_info = {'lastPrice': 145.2, 'previousClose': 144.0, 'currency': 'CAD'}
    mock_ticker_cls.return_value = mock_ticker

    quote = _provider().get_quote('RY.TO')

    assert quote == {'price': 145.2, 'previous_close': 144.0, 'currency': 'CAD'}


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_quote_falls_back_to_history_when_fast_info_has_no_crypto_price(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.fast_info = {'lastPrice': None, 'previousClose': None, 'currency': 'CAD'}
    mock_ticker.history.return_value = pd.DataFrame(
        {'Close': [95_000.0, 98_500.0]},
        index=pd.to_datetime(['2026-08-19', '2026-08-20']),
    )
    mock_ticker_cls.return_value = mock_ticker

    quote = _provider().get_quote('BTC-CAD')

    assert quote == {'price': 98_500.0, 'previous_close': 95_000.0, 'currency': 'CAD'}
    mock_ticker.history.assert_called_once_with(period='5d', interval='1d', auto_adjust=False)


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_quote_falls_back_to_history_when_fast_info_raises(mock_ticker_cls):
    mock_ticker = MagicMock()
    type(mock_ticker).fast_info = property(lambda _self: (_ for _ in ()).throw(KeyError('currentTradingPeriod')))
    mock_ticker.history.return_value = pd.DataFrame(
        {'Close': [34.1, 34.4]},
        index=pd.to_datetime(['2026-08-19', '2026-08-20']),
    )
    mock_ticker_cls.return_value = mock_ticker

    quote = _provider().get_quote('D-UN.TO')

    assert quote['price'] == 34.4
    assert quote['previous_close'] == 34.1
    assert quote['currency'] is None


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_dividends_maps_series_to_dicts(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.dividends = pd.Series(
        [0.5, 0.55],
        index=pd.to_datetime(['2026-03-01', '2026-06-01']),
    )
    mock_ticker.fast_info = {'currency': 'CAD'}
    mock_ticker_cls.return_value = mock_ticker

    events = _provider().get_dividends('RY.TO')

    assert len(events) == 2
    assert events[0]['amount'] == 0.5
    assert events[0]['currency'] == 'CAD'
    assert events[0]['pay_date'] is None
    assert events[0]['ex_date'].isoformat() == '2026-03-01'


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_dividends_returns_empty_list_when_no_history(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.dividends = pd.Series([], dtype=float)
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_dividends('RY.TO') == []


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_calendar_normalizes_dates(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.calendar = {
        'Earnings Date': [date(2026, 8, 27), date(2026, 8, 28)],
        'Ex-Dividend Date': datetime(2026, 8, 20, 9, 30),
        'Dividend Date': pd.Timestamp('2026-09-01'),
    }
    mock_ticker_cls.return_value = mock_ticker

    calendar = _provider().get_calendar('RY.TO')

    assert calendar == {
        'ex_dividend_date': date(2026, 8, 20),
        'dividend_pay_date': date(2026, 9, 1),
        'next_earnings_date': date(2026, 8, 27),
    }


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_calendar_is_none_when_yahoo_has_nothing(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.calendar = {}
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_calendar('RY.TO') is None


def _history_frame():
    return pd.DataFrame(
        {'Close': [100.0, 101.5]},
        index=pd.to_datetime(['2026-08-17', '2026-08-18']),
    )


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_price_history_maps_close_series(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _history_frame()
    mock_ticker_cls.return_value = mock_ticker

    data = _provider().get_price_history('RY.TO', '1Y')

    assert data == [
        {'date': '2026-08-17', 'close': 100.0},
        {'date': '2026-08-18', 'close': 101.5},
    ]
    mock_ticker.history.assert_called_once_with(period='1y')


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_price_history_unknown_range_defaults_to_1y(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _history_frame()
    mock_ticker_cls.return_value = mock_ticker

    _provider().get_price_history('RY.TO', 'bogus')

    mock_ticker.history.assert_called_once_with(period='1y')


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_price_history_empty_when_no_data(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_price_history('RY.TO', '1M') == []


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_price_history_second_call_is_served_from_cache(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _history_frame()
    mock_ticker_cls.return_value = mock_ticker
    provider = _provider()

    provider.get_price_history('RY.TO', '1Y')
    provider.get_price_history('RY.TO', '1Y')

    mock_ticker.history.assert_called_once()


@patch('src.services.market_data.yahoo.time.sleep')
@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_price_history_falls_back_to_stale_cache_on_failure(mock_ticker_cls, mock_sleep):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _history_frame()
    mock_ticker_cls.return_value = mock_ticker
    provider = _provider()
    data = provider.get_price_history('RY.TO', '1Y')

    mock_ticker.history.side_effect = Exception("429 Too Many Requests")
    yahoo_module._price_history_cache[('RY.TO', '1y')] = (0.0, data)  # force-expire

    assert provider.get_price_history('RY.TO', '1Y') == data


def _statements(revenue_by_year, **rows):
    """A yfinance-shaped statement frame: line items as the index, fiscal
    year-ends as columns, newest first."""
    columns = [pd.Timestamp(f'{year}-12-31') for year in sorted(revenue_by_year, reverse=True)]
    data = {'Total Revenue': [revenue_by_year[c.year] for c in columns]}
    for label, value in rows.items():
        data[label.replace('_', ' ')] = [value] * len(columns)
    return pd.DataFrame(data, index=columns).T


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_statement_metrics_maps_balance_and_income_lines(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.income_stmt = _statements(
        {2022: 100.0, 2023: 110.0, 2024: 120.0, 2025: 133.1},
        EBIT=40.0, EBITDA=55.0, **{'Tax Rate For Calcs': 0.26},
    )
    mock_ticker.balance_sheet = _statements(
        {2025: 0.0},
        **{
            'Total Assets': 500.0,
            'Total Liabilities Net Minority Interest': 300.0,
            'Stockholders Equity': 200.0,
        },
    )
    mock_ticker_cls.return_value = mock_ticker

    metrics = _provider().get_statement_metrics('RY.TO')

    assert metrics['revenue'] == 133.1
    assert metrics['ebit'] == 40.0
    assert metrics['ebitda'] == 55.0
    assert metrics['total_assets'] == 500.0
    assert metrics['total_liabilities'] == 300.0
    assert metrics['total_equity'] == 200.0
    assert metrics['tax_rate'] == 0.26


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_statement_metrics_falls_back_to_alias_line_names(mock_ticker_cls):
    """Yahoo names the same line differently across companies."""
    mock_ticker = MagicMock()
    mock_ticker.income_stmt = _statements({2025: 90.0}, **{'Operating Income': 12.0})
    mock_ticker.balance_sheet = _statements(
        {2025: 0.0}, **{'Total Equity Gross Minority Interest': 45.0},
    )
    mock_ticker_cls.return_value = mock_ticker

    metrics = _provider().get_statement_metrics('RY.TO')

    assert metrics['ebit'] == 12.0
    assert metrics['total_equity'] == 45.0


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_revenue_cagr_reports_the_span_it_actually_measured(mock_ticker_cls):
    """Free Yahoo statements carry an empty oldest column for most companies,
    so the CAGR covers fewer years than the frame suggests — the span is
    returned so the label can't overstate it."""
    mock_ticker = MagicMock()
    mock_ticker.income_stmt = _statements(
        {2021: float('nan'), 2022: 100.0, 2023: 110.0, 2024: 120.0, 2025: 133.1}
    )
    mock_ticker.balance_sheet = _statements({2025: 0.0}, **{'Total Assets': 1.0})
    mock_ticker_cls.return_value = mock_ticker

    metrics = _provider().get_statement_metrics('RY.TO')

    assert metrics['revenue_cagr_years'] == 3
    assert metrics['revenue_cagr'] == pytest.approx(0.1, abs=1e-3)


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_statement_metrics_returns_none_when_statements_are_empty(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.income_stmt = pd.DataFrame()
    mock_ticker.balance_sheet = pd.DataFrame()
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_statement_metrics('RY.TO') is None


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_get_fundamentals_derives_net_debt_from_debt_and_cash(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.get_info.return_value = {
        'totalDebt': 900.0, 'totalCash': 250.0, 'bookValue': 12.5,
        'enterpriseValue': 4000.0, 'ebitdaMargins': 0.31,
    }
    mock_ticker_cls.return_value = mock_ticker

    data = _provider().get_fundamentals('RY.TO')

    assert data['net_debt'] == 650.0
    assert data['total_debt'] == 900.0
    assert data['book_value_per_share'] == 12.5
    assert data['enterprise_value'] == 4000.0
    assert data['ebitda_margin'] == 0.31


@patch('src.services.market_data.yahoo.yf.Ticker')
def test_net_debt_is_none_when_yahoo_reports_no_debt_figure(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.get_info.return_value = {'totalCash': 250.0}
    mock_ticker_cls.return_value = mock_ticker

    assert _provider().get_fundamentals('RY.TO')['net_debt'] is None
