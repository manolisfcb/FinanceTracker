from datetime import date, datetime, timedelta

from src.extensions import db, scheduler
from src.models import Asset, CompanyEvent, CompanyEventKind
from src.resources.jobs._common import run_job
from src.resources.jobs.refresh_dividends import held_assets
from src.services import edgar
from src.services.market_data import get_provider

US_EXCHANGES = {"US", "NYSE", "NASDAQ"}
FILING_LOOKBACK_DAYS = 400


def _ingest_filings(asset: Asset) -> int:
    if asset.cik is None:
        asset.cik = edgar.resolve_cik(asset.symbol)
        if asset.cik is None:
            return 0

    cutoff = date.today() - timedelta(days=FILING_LOOKBACK_DAYS)
    created = 0
    for filing in edgar.get_recent_filings(asset.cik):
        filed_on = date.fromisoformat(filing["filing_date"])
        if filed_on < cutoff:
            continue
        exists = CompanyEvent.query.filter_by(
            asset_id=asset.id, source="EDGAR", external_id=filing["accession_number"]
        ).first()
        if exists is not None:
            continue

        db.session.add(
            CompanyEvent(
                asset_id=asset.id,
                kind=CompanyEventKind.FILING,
                source="EDGAR",
                external_id=filing["accession_number"],
                title=f"{asset.symbol} — {filing['form']}",
                summary=f"Nuevo {filing['form']} en SEC EDGAR.",
                url=filing["url"],
                published_at=datetime.combine(filed_on, datetime.min.time()),
                event_date=filed_on,
            )
        )
        created += 1
    return created


def _upsert_next_earnings(asset: Asset, earnings_date: date):
    # Singleton per asset: the estimated date shifts as the company confirms
    # it, so the row is updated in place instead of accumulating one per run.
    external_id = f"earnings-next:{asset.id}"
    event = CompanyEvent.query.filter_by(
        asset_id=asset.id, source="YAHOO", external_id=external_id
    ).first()
    if event is None:
        event = CompanyEvent(
            asset_id=asset.id,
            kind=CompanyEventKind.EARNINGS,
            source="YAHOO",
            external_id=external_id,
        )
        db.session.add(event)
    event.title = f"{asset.symbol} — resultados"
    event.summary = f"Próxima fecha de resultados: {earnings_date.isoformat()}"
    event.published_at = datetime.utcnow()
    event.event_date = earnings_date


def _refresh_company_events():
    provider = get_provider()
    items = 0
    for asset in held_assets():
        if asset.exchange in US_EXCHANGES:
            _ingest_filings(asset)

        calendar = provider.get_calendar(asset.yahoo_symbol)
        if calendar and calendar.get("next_earnings_date"):
            _upsert_next_earnings(asset, calendar["next_earnings_date"])
        items += 1
    return items


@scheduler.task('cron', id='refresh_company_events', hour=19, minute=0, timezone='America/Toronto')
def refresh_company_events():
    """SEC EDGAR filings (US holdings) and next earnings date (all holdings).

    Canada has no equivalent: SEDAR+ has no public API, so CA assets only get
    the earnings date here and a SEDAR+ search link in the UI.
    """
    with scheduler.app.app_context():
        run_job('refresh_company_events', _refresh_company_events)
