from src.services.market_data.base import MarketDataProvider
from src.services.market_data.yahoo import YahooProvider

_PROVIDERS = {
    "yahoo": YahooProvider,
}


def get_provider(name: str | None = None, **kwargs) -> MarketDataProvider:
    """Factory for the configured MarketDataProvider (config.MARKET_DATA_PROVIDER).

    `kwargs` are forwarded to the provider's constructor — e.g. a request
    handler that can't afford the default retry/backoff latency can ask for
    `get_provider(max_retries=1, min_interval_seconds=0)`.
    """
    from flask import current_app

    name = name or current_app.config.get("MARKET_DATA_PROVIDER", "yahoo")
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown MARKET_DATA_PROVIDER '{name}'. Available: {list(_PROVIDERS)}"
        )
    return provider_cls(**kwargs)
