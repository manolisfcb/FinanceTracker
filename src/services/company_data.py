"""Ingest of per-company data: dividends, calendar, filings and news.

Two callers write through here, so both produce identical rows:

* the freshness-driven daily asset-data job;
* the company page, which backfills an asset the first time someone opens
  it — otherwise the ~1100 universe assets nobody owns would stay blank.
"""
import hashlib
import re
import time
from datetime import date, datetime, timedelta

from src.extensions import db
from src.models import (
    CompanyEvent,
    CompanyEventKind,
    DividendHistory,
)
from src.services import edgar
from src.services.market_data import get_provider
from src.services.news import get_news_providers

US_EXCHANGES = {"US", "NYSE", "NASDAQ"}
FILING_LOOKBACK_DAYS = 400
NEWS_PER_PROVIDER_LIMIT = 10
# Yahoo and Google surface the same wire story under different URLs, so URL
# dedupe alone isn't enough — titles are compared within this window too.
NEWS_TITLE_DEDUPE_DAYS = 14
# How long before an on-demand backfill retries an asset. Bounds the cost of
# an asset whose sources genuinely have nothing to return.
BACKFILL_TTL_SECONDS = 6 * 3600

_NON_ALNUM = re.compile(r'[^a-z0-9]+')

# Corporate suffixes and filler carry no identifying signal, so they're not
# usable to tell whether a story is actually about the company.
_NAME_STOPWORDS = {
    'inc', 'corp', 'corporation', 'company', 'co', 'ltd', 'limited', 'plc',
    'sa', 's', 'a', 'the', 'of', 'and', 'group', 'holdings', 'holding',
    'participacoes', 'participações', 'energia', 'brasil',
}

_backfill_attempts: dict[int, float] = {}


# -- dividends --------------------------------------------------------------

def _upsert_history(asset_id: int, event: dict):
    row = DividendHistory.query.filter_by(asset_id=asset_id, ex_date=event["ex_date"]).first()
    if row is None:
        row = DividendHistory(asset_id=asset_id, ex_date=event["ex_date"])
        db.session.add(row)
    row.pay_date = event.get("pay_date")
    row.amount = event["amount"]
    row.currency = event["currency"]


def _upsert_singleton_event(asset, kind, external_id, title, summary, event_date):
    """One row per asset per kind, updated in place: announced dates move as
    the company confirms them, and a row per fetch would pile up duplicates.
    """
    event = CompanyEvent.query.filter_by(
        asset_id=asset.id, source="YAHOO", external_id=external_id
    ).first()
    if event is None:
        event = CompanyEvent(
            asset_id=asset.id, kind=kind, source="YAHOO", external_id=external_id
        )
        db.session.add(event)
    event.title = title
    event.summary = summary
    event.published_at = datetime.utcnow()
    event.event_date = event_date


def ingest_dividends(asset, provider) -> int:
    events = provider.get_dividends(asset.yahoo_symbol)
    for event in events:
        _upsert_history(asset.id, event)
    return len(events)


def ingest_calendar(asset, provider) -> int:
    calendar = provider.get_calendar(asset.yahoo_symbol)
    if not calendar:
        return 0

    written = 0
    ex_date = calendar.get("ex_dividend_date")
    if ex_date and ex_date >= date.today():
        pay_date = calendar.get("dividend_pay_date")
        _upsert_singleton_event(
            asset,
            CompanyEventKind.DIVIDEND,
            f"dividend-next:{asset.id}",
            f"{asset.symbol} — dividendo anunciado",
            f"Ex-date {ex_date.isoformat()}"
            + (f", pago {pay_date.isoformat()}" if pay_date else ""),
            ex_date,
        )
        written += 1

    earnings_date = calendar.get("next_earnings_date")
    if earnings_date:
        _upsert_singleton_event(
            asset,
            CompanyEventKind.EARNINGS,
            f"earnings-next:{asset.id}",
            f"{asset.symbol} — resultados",
            f"Próxima fecha de resultados: {earnings_date.isoformat()}",
            earnings_date,
        )
        written += 1
    return written


# -- SEC filings ------------------------------------------------------------

def ingest_filings(asset) -> int:
    """US filings only. Canada has no equivalent: SEDAR+ has no public API,
    so CA assets get a SEDAR+ search link in the UI instead."""
    if asset.exchange not in US_EXCHANGES:
        return 0

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

        db.session.add(CompanyEvent(
            asset_id=asset.id,
            kind=CompanyEventKind.FILING,
            source="EDGAR",
            external_id=filing["accession_number"],
            title=f"{asset.symbol} — {filing['form']}",
            summary=f"Nuevo {filing['form']} en SEC EDGAR.",
            url=filing["url"],
            published_at=datetime.combine(filed_on, datetime.min.time()),
            event_date=filed_on,
        ))
        created += 1
    return created


# -- news -------------------------------------------------------------------

def _url_hash(url: str) -> str:
    return hashlib.sha1(url.encode('utf-8')).hexdigest()


def _normalize_title(title: str) -> str:
    return _NON_ALNUM.sub(' ', title.lower()).strip()


def _name_phrase(asset) -> str:
    """The first couple of identifying words of the company name."""
    tokens = [t for t in _NON_ALNUM.split(asset.name.lower()) if t and t not in _NAME_STOPWORDS]
    phrase = ' '.join(tokens[:2])
    return phrase if len(phrase) >= 4 else ''


def is_about_asset(asset, story) -> bool:
    """Yahoo's per-ticker feed mixes in loosely related market stories (asking
    for RY returns Rayonier and Citizens & Northern), and Google surfaces bond
    reference pages. Requiring the ticker or the company name in the headline
    or summary keeps a company feed about that company.
    """
    text = _normalize_title(f"{story['title']} {story.get('summary') or ''}")
    if f" {asset.symbol.lower()} " in f" {text} ":
        return True
    phrase = _name_phrase(asset)
    return bool(phrase) and phrase in text


def _recent_titles(asset_id: int, since: datetime) -> set[str]:
    rows = (
        CompanyEvent.query
        .filter(
            CompanyEvent.asset_id == asset_id,
            CompanyEvent.kind == CompanyEventKind.NEWS,
            CompanyEvent.published_at >= since,
        )
        .with_entities(CompanyEvent.title)
        .all()
    )
    return {_normalize_title(row[0]) for row in rows}


def ingest_news(asset, providers) -> int:
    now = datetime.utcnow()
    seen_titles = _recent_titles(asset.id, now - timedelta(days=NEWS_TITLE_DEDUPE_DAYS))
    created = 0

    for provider in providers:
        for story in provider.get_news(asset, limit=NEWS_PER_PROVIDER_LIMIT):
            if not is_about_asset(asset, story):
                continue

            external_id = _url_hash(story["url"])
            exists = CompanyEvent.query.filter_by(
                asset_id=asset.id, source=provider.name, external_id=external_id
            ).first()
            if exists is not None:
                continue

            normalized = _normalize_title(story["title"])
            if normalized in seen_titles:
                continue
            seen_titles.add(normalized)

            source_name = story.get("source_name")
            db.session.add(CompanyEvent(
                asset_id=asset.id,
                kind=CompanyEventKind.NEWS,
                source=provider.name,
                external_id=external_id,
                # No symbol prefix (unlike FILING/EARNINGS titles): the UI
                # already shows the company, and the headline is the payload.
                title=story["title"][:255],
                summary=story.get("summary") or (
                    f"Publicado por {source_name}." if source_name else None
                ),
                url=story["url"],
                published_at=story.get("published_at") or now,
            ))
            created += 1
    return created


# -- on-demand backfill (company page) --------------------------------------

def needs_backfill(asset) -> bool:
    """Whether a company page should try to fill this asset in.

    Checks dividends and news separately rather than "has any row at all":
    an asset can end up half-filled (EDGAR succeeded, Yahoo didn't), and a
    single-row check would leave it that way forever. Companies that
    genuinely have neither are re-attempted at most once per BACKFILL_TTL.
    """
    has_dividends = DividendHistory.query.filter_by(asset_id=asset.id).first() is not None
    has_news = CompanyEvent.query.filter_by(
        asset_id=asset.id, kind=CompanyEventKind.NEWS
    ).first() is not None
    return not (has_dividends and has_news)


def backfill_asset(asset) -> bool:
    """Fetch everything for one asset, for a company page with no data yet.

    Returns whether a fetch was attempted. Capped retries and no throttling
    (same trade-off as the page's live quote): a slow source must not stall
    the page. Never raises — a failed backfill just leaves the page empty.
    """
    last_attempt = _backfill_attempts.get(asset.id)
    if last_attempt and (time.monotonic() - last_attempt) < BACKFILL_TTL_SECONDS:
        return False
    # Recorded before fetching, so a failing asset isn't retried on every view.
    _backfill_attempts[asset.id] = time.monotonic()

    try:
        now = datetime.utcnow()
        provider = get_provider(max_retries=1, min_interval_seconds=0)
        ingest_dividends(asset, provider)
        ingest_calendar(asset, provider)
        asset.last_dividend_refresh_at = now
        ingest_filings(asset)
        asset.last_filings_refresh_at = now
        ingest_news(asset, get_news_providers())
        asset.last_news_refresh_at = now
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        print(f"[company_data] backfill failed for {asset.symbol}: {exc}")
        return False
    return True
