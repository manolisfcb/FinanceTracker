"""The site-wide market strip: index levels, USD/CAD, BoC rate, TSX status.

Values are refreshed by the daily market job and read from `MarketIndicator`, so
rendering the strip on every page costs one small query and never a provider
call.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import current_app

from src.extensions import db
from src.models import MarketIndicator
from src.services.market_data import get_provider

TORONTO = ZoneInfo("America/Toronto")

# Yahoo index symbols. The strip is deliberately short: two North American
# benchmarks plus NASDAQ is what a Canadian investor glances at.
INDEX_SYMBOLS = [
    ("tsx", "S&P/TSX", "^GSPTSE"),
    ("sp500", "S&P 500", "^GSPC"),
    ("nasdaq", "NASDAQ", "^IXIC"),
]

USDCAD_KEY = "usdcad"
BOC_RATE_KEY = "boc_rate"

# Valet series for the Bank of Canada's target for the overnight rate.
BOC_POLICY_RATE_SERIES = "V39079"
VALET_URL = "https://www.bankofcanada.ca/valet/observations/{series}/json"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrueNorthAnalytics/1.0)"}

TSX_OPEN = time(9, 30)
TSX_CLOSE = time(16, 0)

# Statutory closures of the TSX. Not derivable from a weekday rule, and
# showing "abierto" on Canada Day is worse than showing nothing.
TSX_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 18),
    date(2026, 7, 1),
    date(2026, 8, 3),
    date(2026, 9, 7),
    date(2026, 10, 12),
    date(2026, 11, 11),
    date(2026, 12, 25),
    date(2026, 12, 28),
}


def _upsert(key, label, value, change_percent=None):
    row = MarketIndicator.query.get(key)
    if row is None:
        row = MarketIndicator(key=key)
        db.session.add(row)
    row.label = label
    row.value = value
    row.change_percent = change_percent
    row.updated_at = datetime.utcnow()
    return row


def fetch_boc_policy_rate() -> float | None:
    """Latest target for the overnight rate, as a percentage (2.75 → 2.75%)."""
    response = requests.get(
        VALET_URL.format(series=BOC_POLICY_RATE_SERIES),
        params={"recent": 1},
        headers=_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    observations = response.json().get("observations") or []
    if not observations:
        return None
    raw = observations[-1].get(BOC_POLICY_RATE_SERIES, {}).get("v")
    return None if raw is None else float(raw)


def refresh_market_indicators() -> int:
    """Refresh every strip figure; returns how many were updated.

    Each source is isolated: a Yahoo outage must not cost us the BoC rate,
    and vice versa, because a strip with three of five figures still beats an
    empty one.
    """
    provider = get_provider()
    updated = 0

    for key, label, symbol in INDEX_SYMBOLS:
        try:
            quote = provider.get_quote(symbol)
        except Exception:
            current_app.logger.warning("market strip: quote failed for %s", symbol)
            continue
        if not quote or quote.get("price") is None:
            continue

        price = quote["price"]
        previous_close = quote.get("previous_close")
        change_percent = (
            (price - previous_close) / previous_close * 100
            if previous_close
            else None
        )
        _upsert(key, label, price, change_percent)
        updated += 1

    from src.services.fx import latest_fx_rate_to_cad

    try:
        usdcad = latest_fx_rate_to_cad("USD")
    except Exception:
        usdcad = None
    if usdcad is not None:
        _upsert(USDCAD_KEY, "USD/CAD", usdcad)
        updated += 1

    try:
        boc_rate = fetch_boc_policy_rate()
    except Exception:
        current_app.logger.warning("market strip: Bank of Canada rate unavailable")
        boc_rate = None
    if boc_rate is not None:
        _upsert(BOC_RATE_KEY, "Tasa BoC", boc_rate)
        updated += 1

    return updated


def tsx_session(now: datetime | None = None) -> dict:
    """Whether the TSX is trading right now, and the phrase to render.

    `now` is accepted so this is testable without freezing the clock; it is
    interpreted in Toronto time, which is the only timezone the strip claims.
    """
    moment = (now or datetime.now(TORONTO)).astimezone(TORONTO)
    today = moment.date()
    is_business_day = moment.weekday() < 5 and today not in TSX_HOLIDAYS_2026
    is_open = is_business_day and TSX_OPEN <= moment.time() < TSX_CLOSE

    if is_open:
        return {"is_open": True, "text": "TSX abierto · cierra 16:00 ET"}
    if is_business_day and moment.time() < TSX_OPEN:
        return {"is_open": False, "text": "TSX cerrado · abre 9:30 ET"}
    return {"is_open": False, "text": f"TSX cerrado · abre {_next_open_label(today)} 9:30 ET"}


_WEEKDAYS_ES = ["el lunes", "el martes", "el miércoles", "el jueves", "el viernes"]


def _next_open_label(today: date) -> str:
    candidate = today + timedelta(days=1)
    for _ in range(10):
        if candidate.weekday() < 5 and candidate not in TSX_HOLIDAYS_2026:
            return "mañana" if candidate == today + timedelta(days=1) else _WEEKDAYS_ES[candidate.weekday()]
        candidate += timedelta(days=1)
    return "próximamente"


def market_strip_context() -> dict:
    """Indicators plus session status, in the order the strip renders them.

    Keep every slot present before the first refresh (or during a partial
    provider outage). A missing value is rendered as an em dash; it must never
    be replaced with a made-up market figure.
    """
    rows = {row.key: row for row in MarketIndicator.query.all()}
    indices = [
        rows.get(key)
        or {
            "key": key,
            "label": label,
            "value": None,
            "change_percent": None,
        }
        for key, label, _ in INDEX_SYMBOLS
    ]
    return {
        "market_indices": indices,
        "market_usdcad": rows.get(USDCAD_KEY)
        or {
            "key": USDCAD_KEY,
            "label": "USD/CAD",
            "value": None,
            "change_percent": None,
        },
        "market_boc_rate": rows.get(BOC_RATE_KEY)
        or {
            "key": BOC_RATE_KEY,
            "label": "Tasa BoC",
            "value": None,
            "change_percent": None,
        },
        "market_session": tsx_session(),
    }
