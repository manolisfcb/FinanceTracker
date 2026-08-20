import hashlib
import re
from datetime import datetime, timedelta

from src.extensions import db, scheduler
from src.models import CompanyEvent, CompanyEventKind
from src.resources.jobs._common import run_job
from src.resources.jobs.refresh_dividends import held_assets
from src.services.news import get_news_providers

PER_PROVIDER_LIMIT = 10
# Yahoo and Google surface the same wire story under different URLs, so URL
# dedupe alone isn't enough — titles are compared within this window too.
TITLE_DEDUPE_DAYS = 14

_NON_ALNUM = re.compile(r'[^a-z0-9]+')

# Corporate suffixes and filler carry no identifying signal, so they're not
# usable to tell whether a story is actually about the company.
_NAME_STOPWORDS = {
    'inc', 'corp', 'corporation', 'company', 'co', 'ltd', 'limited', 'plc',
    'sa', 's', 'a', 'the', 'of', 'and', 'group', 'holdings', 'holding',
    'participacoes', 'participações', 'energia', 'brasil',
}


def _url_hash(url: str) -> str:
    return hashlib.sha1(url.encode('utf-8')).hexdigest()


def _normalize_title(title: str) -> str:
    return _NON_ALNUM.sub(' ', title.lower()).strip()


def _name_phrase(asset) -> str:
    """The first couple of identifying words of the company name."""
    tokens = [t for t in _NON_ALNUM.split(asset.name.lower()) if t and t not in _NAME_STOPWORDS]
    phrase = ' '.join(tokens[:2])
    return phrase if len(phrase) >= 4 else ''


def _is_about_asset(asset, story) -> bool:
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


def _ingest_for_asset(asset, providers) -> int:
    now = datetime.utcnow()
    seen_titles = _recent_titles(asset.id, now - timedelta(days=TITLE_DEDUPE_DAYS))
    created = 0

    for provider in providers:
        for story in provider.get_news(asset, limit=PER_PROVIDER_LIMIT):
            if not _is_about_asset(asset, story):
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


def _refresh_all_news():
    providers = get_news_providers()
    if not providers:
        return 0

    items = 0
    for asset in held_assets():
        items += _ingest_for_asset(asset, providers)
    return items


@scheduler.task('interval', id='refresh_news', hours=6)
def refresh_news():
    """Company news for held assets, from every enabled source.

    Interval rather than cron: news breaks through the day, unlike the
    end-of-day fundamentals/FX/snapshot jobs.
    """
    with scheduler.app.app_context():
        run_job('refresh_news', _refresh_all_news)
