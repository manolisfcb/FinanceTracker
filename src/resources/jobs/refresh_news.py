from src.extensions import scheduler
from src.resources.jobs._common import run_job
from src.services.company_data import held_assets, ingest_news
from src.services.news import get_news_providers


def _refresh_all_news():
    providers = get_news_providers()
    if not providers:
        return 0

    items = 0
    for asset in held_assets():
        items += ingest_news(asset, providers)
    return items


@scheduler.task('interval', id='refresh_news', hours=6)
def refresh_news():
    """Company news for held assets, from every enabled source.

    Interval rather than cron: news breaks through the day, unlike the
    end-of-day fundamentals/FX/snapshot jobs.
    """
    with scheduler.app.app_context():
        run_job('refresh_news', _refresh_all_news)
