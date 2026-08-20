from abc import ABC, abstractmethod


class NewsProvider(ABC):
    """Interface for per-company news feeds.

    Same best-effort contract as MarketDataProvider: implementations return an
    empty list (never raise) when a source is unavailable, so one bad symbol
    or a flaky feed can't abort the job's batch.
    """

    #: Stored on CompanyEvent.source — keep short, it's a String(16) column.
    name: str

    @abstractmethod
    def get_news(self, asset, limit: int = 10) -> list[dict]:
        """Recent stories for an asset:
        list of {title, summary, url, published_at, source_name}, newest first.
        `published_at` is a naive UTC datetime, matching the other jobs."""
