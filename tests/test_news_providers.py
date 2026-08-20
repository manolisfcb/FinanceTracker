from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models import Asset
from src.services.news import get_news_providers
from src.services.news.google_news import GoogleNewsProvider
from src.services.news.yahoo_news import YahooNewsProvider

# No network: both feeds are mocked at their point of use.


def _asset():
    return Asset(
        symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD',
        name='Royal Bank of Canada',
    )


YAHOO_STORY = {
    'content': {
        'title': 'RBC beats expectations',
        'summary': 'Royal Bank posted a record quarter.',
        'description': '',
        'pubDate': '2026-08-17T17:10:00Z',
        'provider': {'displayName': 'MarketBeat'},
        'canonicalUrl': {'url': 'https://marketbeat.com/rbc'},
        'clickThroughUrl': {'url': 'https://finance.yahoo.com/rbc'},
    }
}

GOOGLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>RBC nombra nuevo CEO - TradingView</title>
    <link>https://news.google.com/rss/articles/abc123</link>
    <pubDate>Mon, 17 Aug 2026 13:02:00 GMT</pubDate>
    <source url="https://tradingview.com">TradingView</source>
  </item>
  <item>
    <title>Sin fuente conocida</title>
    <link>https://news.google.com/rss/articles/def456</link>
    <pubDate>bogus date</pubDate>
  </item>
</channel></rss>"""


@patch('src.services.news.yahoo_news.yf.Ticker')
def test_yahoo_news_maps_nested_content(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.news = [YAHOO_STORY]
    mock_ticker_cls.return_value = mock_ticker

    items = YahooNewsProvider().get_news(_asset())

    assert items == [{
        'title': 'RBC beats expectations',
        'summary': 'Royal Bank posted a record quarter.',
        'url': 'https://marketbeat.com/rbc',
        'published_at': datetime(2026, 8, 17, 17, 10),
        'source_name': 'MarketBeat',
    }]


@patch('src.services.news.yahoo_news.yf.Ticker')
def test_yahoo_news_skips_stories_without_title_or_url(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.news = [{'content': {'title': '', 'canonicalUrl': {'url': 'https://x'}}},
                        {'content': {'title': 'Sin link'}}]
    mock_ticker_cls.return_value = mock_ticker

    assert YahooNewsProvider().get_news(_asset()) == []


@patch('src.services.news.yahoo_news.yf.Ticker')
def test_yahoo_news_returns_empty_list_on_failure(mock_ticker_cls):
    mock_ticker_cls.side_effect = Exception('429 Too Many Requests')

    assert YahooNewsProvider().get_news(_asset()) == []


@patch('src.services.news.google_news.requests.get')
def test_google_news_parses_rss_and_strips_publisher_suffix(mock_get):
    mock_get.return_value = MagicMock(content=GOOGLE_RSS, raise_for_status=MagicMock())

    items = GoogleNewsProvider().get_news(_asset())

    assert items[0]['title'] == 'RBC nombra nuevo CEO'
    assert items[0]['source_name'] == 'TradingView'
    assert items[0]['published_at'] == datetime(2026, 8, 17, 13, 2)
    assert items[1]['title'] == 'Sin fuente conocida'
    assert items[1]['published_at'] is None


@patch('src.services.news.google_news.requests.get')
def test_google_news_query_uses_name_and_symbol(mock_get):
    mock_get.return_value = MagicMock(content=GOOGLE_RSS, raise_for_status=MagicMock())

    GoogleNewsProvider().get_news(_asset())

    url = mock_get.call_args.args[0]
    assert 'Royal+Bank+of+Canada' in url
    assert 'RY' in url


@patch('src.services.news.google_news.requests.get')
def test_google_news_returns_empty_list_on_bad_xml(mock_get):
    mock_get.return_value = MagicMock(content=b'not xml', raise_for_status=MagicMock())

    assert GoogleNewsProvider().get_news(_asset()) == []


def test_factory_builds_configured_providers(app):
    with app.app_context():
        names = [p.name for p in get_news_providers()]

    assert names == ['YAHOO', 'GOOGLE']


def test_factory_returns_nothing_when_disabled(app):
    with app.app_context():
        assert get_news_providers('') == []


def test_factory_rejects_unknown_provider(app):
    with app.app_context():
        with pytest.raises(ValueError, match='reuters'):
            get_news_providers('reuters')
