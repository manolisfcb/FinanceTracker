import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests

from src.services.news.base import NewsProvider

# Public RSS endpoint — no API key, no quota published. Spanish/Canada
# locale so headlines match the app's UI language.
SEARCH_URL = "https://news.google.com/rss/search?q={query}&hl=es-419&gl=CA&ceid=CA:es-419"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrueNorthAnalytics/1.0)"}


def _parse_pub_date(value):
    """Google's pubDate is RFC 822 ('Mon, 17 Aug 2026 13:02:00 GMT')."""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _split_source(title: str, source_name: str | None):
    """Google appends ' - Publisher' to every headline; drop the duplicate."""
    if source_name and title.endswith(f" - {source_name}"):
        return title[: -(len(source_name) + 3)].strip()
    return title


class GoogleNewsProvider(NewsProvider):
    name = "GOOGLE"

    @staticmethod
    def _query(asset) -> str:
        return quote_plus(f'"{asset.name}" {asset.symbol}')

    def get_news(self, asset, limit: int = 10) -> list[dict]:
        try:
            resp = requests.get(
                SEARCH_URL.format(query=self._query(asset)), headers=_HEADERS, timeout=15
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except (requests.RequestException, ET.ParseError) as exc:
            print(f"[GoogleNewsProvider] {asset.symbol}: {exc}")
            return []

        items = []
        for item in root.findall('./channel/item')[:limit]:
            title = (item.findtext('title') or '').strip()
            url = (item.findtext('link') or '').strip()
            if not title or not url:
                continue

            source_name = item.findtext('source')
            items.append({
                "title": _split_source(title, source_name),
                "summary": None,  # the RSS description is an HTML link blob, not a summary
                "url": url,
                "published_at": _parse_pub_date(item.findtext('pubDate')),
                "source_name": source_name,
            })
        return items
