from datetime import datetime, timezone

import yfinance as yf

from src.services.news.base import NewsProvider


def _parse_pub_date(value):
    """Yahoo's pubDate is ISO-8601 with a trailing Z."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


class YahooNewsProvider(NewsProvider):
    name = "YAHOO"

    def get_news(self, asset, limit: int = 10) -> list[dict]:
        try:
            stories = yf.Ticker(asset.yahoo_symbol).news or []
        except Exception as exc:
            print(f"[YahooNewsProvider] {asset.yahoo_symbol}: {exc}")
            return []

        items = []
        for story in stories[:limit]:
            # yfinance >= 1.0 nests everything under `content`; the flat
            # pre-1.0 shape is gone, so there's no fallback to keep.
            content = story.get("content") or {}
            title = (content.get("title") or "").strip()
            url = (content.get("canonicalUrl") or {}).get("url") or (
                content.get("clickThroughUrl") or {}
            ).get("url")
            if not title or not url:
                continue

            items.append({
                "title": title,
                "summary": (content.get("summary") or content.get("description") or "").strip() or None,
                "url": url,
                "published_at": _parse_pub_date(content.get("pubDate")),
                "source_name": (content.get("provider") or {}).get("displayName"),
            })
        return items
