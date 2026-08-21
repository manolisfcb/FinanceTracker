from datetime import datetime

from src.extensions import scheduler
from src.resources.jobs._common import JobResult, get_or_create_snapshot, run_job, run_operation
from src.services.company_data import ingest_calendar, ingest_dividends, ingest_filings, ingest_news
from src.services.fundamentals import carry_forward_statements, derive_indicators
from src.services.job_policies import (
    fundamentals_universe,
    needs_dividend_refresh,
    needs_filings_refresh,
    needs_fundamentals_refresh,
    needs_news_refresh,
    relevant_assets,
)
from src.services.market_data import get_provider
from src.services.market_prices import record_market_data_failure
from src.services.news import get_news_providers

JOB_NAME = 'daily_asset_data_refresh'


class NoFundamentalsData(RuntimeError):
    pass


# Small direct helpers retained for focused ingestion tests and CLI use. They
# are not scheduler jobs; the only scheduled entry point is the function at
# the bottom of this module.
def _refresh_held_dividends():
    provider = get_provider()
    items = 0
    for asset in relevant_assets():
        items += ingest_dividends(asset, provider)
        items += ingest_calendar(asset, provider)
    return items


def _refresh_filings():
    return sum(ingest_filings(asset) for asset in relevant_assets())


def _refresh_all_news():
    providers = get_news_providers()
    if not providers:
        return 0
    return sum(ingest_news(asset, providers) for asset in relevant_assets())


def _refresh_dividend_data(asset, provider, now):
    items = ingest_dividends(asset, provider) + ingest_calendar(asset, provider)
    asset.last_dividend_refresh_at = now
    return items


def _refresh_fundamentals_data(asset, provider, now):
    try:
        data = provider.get_fundamentals(asset.yahoo_symbol)
    except Exception as exc:
        raise NoFundamentalsData(str(exc)) from exc
    if not data:
        raise NoFundamentalsData('no fundamentals available')
    snapshot = get_or_create_snapshot(asset.id)
    for key, value in data.items():
        # A field Yahoo doesn't return this time must not blank out a value
        # the snapshot already carried forward from a prior day.
        if value is not None:
            setattr(snapshot, key, value)
    carry_forward_statements(asset, snapshot)
    derive_indicators(snapshot)
    asset.last_fundamentals_refresh_at = now
    return 1


def _refresh_filing_data(asset, now):
    items = ingest_filings(asset)
    asset.last_filings_refresh_at = now
    return items


def _refresh_news_data(asset, providers, now):
    items = ingest_news(asset, providers)
    asset.last_news_refresh_at = now
    return items


def _daily_asset_data_refresh():
    now = datetime.utcnow()
    provider = get_provider()
    news_providers = get_news_providers()
    processed = errors = 0

    for asset in relevant_assets(now):
        operations = []
        if needs_dividend_refresh(asset, now):
            operations.append(('dividends_calendar', provider.__class__.__name__,
                               lambda asset=asset: _refresh_dividend_data(asset, provider, now), None))
        if needs_filings_refresh(asset, now):
            operations.append(('filings', 'SEC_EDGAR',
                               lambda asset=asset: _refresh_filing_data(asset, now), None))
        if news_providers and needs_news_refresh(asset, now):
            operations.append(('news', ','.join(p.name for p in news_providers),
                               lambda asset=asset: _refresh_news_data(asset, news_providers, now), None))

        for operation, provider_name, fn, on_error in operations:
            outcome = run_operation(
                JOB_NAME, operation, fn, asset=asset, provider=provider_name, on_error=on_error,
            )
            processed += outcome.items_processed
            errors += not outcome.success

    # Fundamentals sweep the whole listed universe rather than
    # relevant_assets(): the screener lists every company and needs real
    # numbers for all of them, not just what's held or recently viewed.
    for asset in fundamentals_universe():
        if not needs_fundamentals_refresh(asset, now):
            continue
        outcome = run_operation(
            JOB_NAME, 'fundamentals',
            lambda asset=asset: _refresh_fundamentals_data(asset, provider, now),
            asset=asset, provider=provider.__class__.__name__,
            on_error=lambda exc, asset=asset: (
                record_market_data_failure(asset, now)
                if isinstance(exc, NoFundamentalsData) else None
            ),
        )
        processed += outcome.items_processed
        errors += not outcome.success
    return JobResult(processed, errors)


@scheduler.task(
    'cron', id=JOB_NAME, hour=18, minute=15, timezone='America/Toronto',
    misfire_grace_time=3600, coalesce=True, max_instances=1,
)
def daily_asset_data_refresh():
    """Freshness-driven dividends, earnings, fundamentals, filings and news."""
    with scheduler.app.app_context():
        run_job(JOB_NAME, _daily_asset_data_refresh)
