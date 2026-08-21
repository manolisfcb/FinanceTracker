from abc import ABC, abstractmethod


class MarketDataProvider(ABC):
    """Interface for market data providers (profile, quote, fundamentals, dividends).

    Implementations should return None (not raise) when a symbol has no data
    available, so callers (jobs, seed script) can skip and move on instead of
    aborting a batch over one bad symbol.
    """

    @abstractmethod
    def get_profile(self, yahoo_symbol: str) -> dict | None:
        """Company profile: name, sector, industry, country, website, logo_url."""

    @abstractmethod
    def get_quote(self, yahoo_symbol: str) -> dict | None:
        """Latest price snapshot: {price, previous_close, currency}."""

    @abstractmethod
    def get_daily_price(self, yahoo_symbol: str) -> dict | None:
        """Latest daily OHLCV row plus previous_close, date and currency."""

    @abstractmethod
    def get_fundamentals(self, yahoo_symbol: str) -> dict | None:
        """Valuation/profitability/leverage/dividend metrics, keyed like the
        Fundamentals model's columns (pe, pb, roe, debt_to_equity, ...)."""

    @abstractmethod
    def get_statement_metrics(self, yahoo_symbol: str) -> dict | None:
        """Annual balance-sheet and income-statement figures that `info`
        doesn't carry: {revenue, ebit, ebitda, total_assets,
        total_liabilities, total_equity, tax_rate, revenue_cagr,
        revenue_cagr_years}.

        Separate from get_fundamentals() because these come from different,
        slower endpoints and only move once a quarter — callers fetch them on
        demand rather than nightly for the whole universe."""

    @abstractmethod
    def get_dividends(self, yahoo_symbol: str) -> list[dict]:
        """Dividend history: list of {ex_date, pay_date, amount, currency}."""

    @abstractmethod
    def get_calendar(self, yahoo_symbol: str) -> dict | None:
        """Announced upcoming dates:
        {ex_dividend_date, dividend_pay_date, next_earnings_date}.
        Any key may be None when the company hasn't announced that date yet."""

    @abstractmethod
    def get_price_history(self, yahoo_symbol: str, range_key: str) -> list[dict]:
        """EOD close price series for a chart range ('1M', '6M', '1Y', '5Y'):
        list of {date, close}, oldest first."""
