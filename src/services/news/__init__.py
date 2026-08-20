from src.services.news.base import NewsProvider
from src.services.news.google_news import GoogleNewsProvider
from src.services.news.yahoo_news import YahooNewsProvider

_PROVIDERS = {
    "yahoo": YahooNewsProvider,
    "google": GoogleNewsProvider,
}


def get_news_providers(names: str | None = None) -> list[NewsProvider]:
    """The news sources enabled in config.NEWS_PROVIDERS (comma-separated).

    A list rather than a single provider (unlike get_provider): news is
    aggregated from every enabled source at once, not swapped between.
    """
    from flask import current_app

    names = names if names is not None else current_app.config.get("NEWS_PROVIDERS", "")
    providers = []
    for name in (n.strip().lower() for n in names.split(",")):
        if not name:
            continue
        try:
            providers.append(_PROVIDERS[name]())
        except KeyError:
            raise ValueError(
                f"Unknown news provider '{name}'. Available: {list(_PROVIDERS)}"
            )
    return providers
