import random
import time
from datetime import date, datetime

import yfinance as yf

from src.services.market_data.base import MarketDataProvider

# yfinance period string + cache TTL per chart range. A fresh YahooProvider
# is built per request (see get_provider()), so the cache lives at module
# level, keyed by (yahoo_symbol, range_key), to actually survive across
# requests and cut down on Yahoo calls for a popular symbol.
_PRICE_HISTORY_PERIODS = {
    "1M": "1mo",
    "6M": "6mo",
    "1Y": "1y",
    "5Y": "5y",
}
_PRICE_HISTORY_CACHE_TTL_SECONDS = 900
_price_history_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


def _as_fraction(percent_value):
    return percent_value / 100 if percent_value is not None else None


def _as_date(value):
    """yfinance's calendar mixes date, datetime and pandas Timestamp."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return value.date() if hasattr(value, "date") else None


class YahooProvider(MarketDataProvider):
    """yfinance-backed MarketDataProvider. Free, unofficial, rate-limited by
    Yahoo on their end — retries with backoff and a minimum interval between
    calls are the mitigation available without a paid provider."""

    def __init__(self, max_retries: int = 3, min_interval_seconds: float = 0.5):
        self.max_retries = max_retries
        self.min_interval_seconds = min_interval_seconds
        self._last_call = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        wait = self.min_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _with_retries(self, fn):
        last_error = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                return fn()
            except Exception as exc:
                last_error = exc
                time.sleep(random.uniform(1, 3))
        print(f"[YahooProvider] giving up after {self.max_retries} attempts: {last_error}")
        return None

    @staticmethod
    def _ticker(yahoo_symbol: str):
        return yf.Ticker(yahoo_symbol)

    def get_profile(self, yahoo_symbol: str) -> dict | None:
        info = self._with_retries(lambda: self._ticker(yahoo_symbol).get_info())
        return self._map_profile(info) if info else None

    def get_quote(self, yahoo_symbol: str) -> dict | None:
        def _fetch():
            fast = self._ticker(yahoo_symbol).fast_info
            return {
                "price": fast.get("lastPrice"),
                "previous_close": fast.get("previousClose"),
                "currency": fast.get("currency"),
            }
        return self._with_retries(_fetch)

    def get_fundamentals(self, yahoo_symbol: str) -> dict | None:
        info = self._with_retries(lambda: self._ticker(yahoo_symbol).get_info())
        return self._map_fundamentals(info) if info else None

    def get_profile_and_fundamentals(self, yahoo_symbol: str) -> tuple[dict | None, dict | None]:
        """profile + fundamentals from a single get_info() call — callers
        that need both should use this instead of calling get_profile() and
        get_fundamentals() separately, which would fetch the same payload twice."""
        info = self._with_retries(lambda: self._ticker(yahoo_symbol).get_info())
        if not info:
            return None, None
        return self._map_profile(info), self._map_fundamentals(info)

    @staticmethod
    def _map_profile(info: dict) -> dict:
        website = info.get("website")
        return {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "website": website,
            "logo_url": YahooProvider._logo_url(website),
            "description": info.get("longBusinessSummary"),
        }

    @staticmethod
    def _map_fundamentals(info: dict) -> dict:
        return {
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb": info.get("priceToBook"),
            "ps": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            # Not exposed by yfinance's `info` dict (would need deriving from
            # financial statements) — left None rather than approximated.
            "roic": None,
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "net_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            # yfinance >=1.6 returns dividendYield as a percent-scale number
            # (1.65 meaning 1.65%), unlike every other ratio in `info`
            # (roe/margins/payoutRatio are 0-1 fractions) — normalize to the
            # same 0-1 fraction convention so the `percent` display filter
            # (which multiplies by 100) is correct for every field uniformly.
            "dividend_yield": _as_fraction(info.get("dividendYield")),
            "payout_ratio": info.get("payoutRatio"),
            "dividend_rate": info.get("dividendRate"),
            "eps": info.get("trailingEps"),
            # yfinance has no literal 5-year CAGR field; closest available is
            # the YoY growth figure. Documented simplification (plan 1.1).
            "eps_growth_5y": info.get("earningsGrowth"),
            "revenue_growth_5y": info.get("revenueGrowth"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        }

    def get_dividends(self, yahoo_symbol: str) -> list[dict]:
        def _fetch():
            ticker = self._ticker(yahoo_symbol)
            series = ticker.dividends
            if series is None or series.empty:
                return []
            currency = ticker.fast_info.get("currency")
            events = []
            for ex_date, amount in series.items():
                events.append({
                    "ex_date": ex_date.date() if hasattr(ex_date, "date") else ex_date,
                    "pay_date": None,  # yfinance's dividend series has no pay-date field
                    "amount": float(amount),
                    "currency": currency,
                })
            return events
        return self._with_retries(_fetch) or []

    def get_calendar(self, yahoo_symbol: str) -> dict | None:
        def _fetch():
            calendar = self._ticker(yahoo_symbol).calendar
            if not calendar:
                return None
            earnings = calendar.get("Earnings Date")
            if isinstance(earnings, (list, tuple)):
                earnings = earnings[0] if earnings else None
            return {
                "ex_dividend_date": _as_date(calendar.get("Ex-Dividend Date")),
                "dividend_pay_date": _as_date(calendar.get("Dividend Date")),
                "next_earnings_date": _as_date(earnings),
            }
        return self._with_retries(_fetch)

    def get_price_history(self, yahoo_symbol: str, range_key: str) -> list[dict]:
        period = _PRICE_HISTORY_PERIODS.get(range_key, _PRICE_HISTORY_PERIODS["1Y"])
        cache_key = (yahoo_symbol, period)
        cached = _price_history_cache.get(cache_key)
        if cached and (time.monotonic() - cached[0]) < _PRICE_HISTORY_CACHE_TTL_SECONDS:
            return cached[1]

        def _fetch():
            history = self._ticker(yahoo_symbol).history(period=period)
            if history is None or history.empty:
                return []
            return [
                {"date": ts.date().isoformat(), "close": float(row["Close"])}
                for ts, row in history.iterrows()
            ]

        data = self._with_retries(_fetch)
        if data is None:
            return cached[1] if cached else []
        _price_history_cache[cache_key] = (time.monotonic(), data)
        return data

    @staticmethod
    def _logo_url(website: str | None) -> str | None:
        """Best-effort logo via Clearbit's free logo API (no key required,
        derived from the company's own domain) — yfinance no longer returns
        a logo URL directly in `info`."""
        if not website:
            return None
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]
        domain = domain.replace("www.", "").strip()
        return f"https://logo.clearbit.com/{domain}" if domain else None
