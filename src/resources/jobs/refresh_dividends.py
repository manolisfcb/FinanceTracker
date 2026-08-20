from datetime import date, datetime

from src.extensions import db, scheduler
from src.models import Asset, CompanyEvent, CompanyEventKind, DividendHistory, OrderModel
from src.resources.jobs._common import run_job
from src.services.market_data import get_provider


def held_assets():
    """Assets any user has ever ordered.

    Dividend data is only fetched for these, not for the whole universe —
    Yahoo rate-limits, and nothing outside a portfolio needs it yet.
    """
    asset_ids = {
        row[0] for row in OrderModel.query.with_entities(OrderModel.asset_id).distinct().all()
    }
    if not asset_ids:
        return []
    return Asset.query.filter(Asset.id.in_(asset_ids)).all()


def _upsert_history(asset_id: int, event: dict):
    row = DividendHistory.query.filter_by(asset_id=asset_id, ex_date=event["ex_date"]).first()
    if row is None:
        row = DividendHistory(asset_id=asset_id, ex_date=event["ex_date"])
        db.session.add(row)
    row.pay_date = event.get("pay_date")
    row.amount = event["amount"]
    row.currency = event["currency"]


def _upsert_upcoming_dividend(asset: Asset, calendar: dict):
    ex_date = calendar.get("ex_dividend_date")
    if ex_date is None or ex_date < date.today():
        return

    # One row per asset, updated in place: the announced ex-date moves each
    # quarter and a new row per fetch would pile up stale duplicates.
    external_id = f"dividend-next:{asset.id}"
    event = CompanyEvent.query.filter_by(
        asset_id=asset.id, source="YAHOO", external_id=external_id
    ).first()
    if event is None:
        event = CompanyEvent(
            asset_id=asset.id,
            kind=CompanyEventKind.DIVIDEND,
            source="YAHOO",
            external_id=external_id,
        )
        db.session.add(event)

    pay_date = calendar.get("dividend_pay_date")
    event.title = f"{asset.symbol} — dividendo anunciado"
    event.summary = (
        f"Ex-date {ex_date.isoformat()}"
        + (f", pago {pay_date.isoformat()}" if pay_date else "")
    )
    event.published_at = datetime.utcnow()
    event.event_date = ex_date


def _refresh_held_dividends():
    provider = get_provider()
    items = 0
    for asset in held_assets():
        for event in provider.get_dividends(asset.yahoo_symbol):
            _upsert_history(asset.id, event)
        calendar = provider.get_calendar(asset.yahoo_symbol)
        if calendar:
            _upsert_upcoming_dividend(asset, calendar)
        items += 1
    return items


@scheduler.task('cron', id='refresh_dividends', hour=17, minute=30, timezone='America/Toronto')
def refresh_dividends():
    """Dividend history and the next announced ex-date for held assets.

    Runs before refresh_snapshots (20:00), which turns this history into
    per-user suggested DividendReceived rows.
    """
    with scheduler.app.app_context():
        run_job('refresh_dividends', _refresh_held_dividends)
