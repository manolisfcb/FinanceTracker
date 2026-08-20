"""Exchange-rate lookup with a persistent Bank of Canada fallback."""

from datetime import date, timedelta

import requests
from flask import current_app

from src.extensions import db
from src.models import FxRate

VALET_OBSERVATIONS_URL = "https://www.bankofcanada.ca/valet/observations/{series}/json"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrueNorthAnalytics/1.0)"}
_LOOKBACK_DAYS = 7
_SERIES_BY_CURRENCY = {"USD": "FXUSDCAD"}


def fetch_rates_to_cad(currency: str, start_date: date, end_date: date) -> list[FxRate]:
    """Fetch and cache Bank of Canada observations in an inclusive date range.

    The caller owns the database transaction. Network and response errors are
    allowed to bubble up so scheduled jobs can record a failed run; the
    user-facing lookup below handles them without turning an order POST into a
    server error.
    """
    normalized_currency = currency.strip().upper()
    if normalized_currency == "CAD":
        return []

    try:
        series = _SERIES_BY_CURRENCY[normalized_currency]
    except KeyError as exc:
        raise ValueError(f"Unsupported FX conversion: {normalized_currency}->CAD") from exc

    pair = f"{normalized_currency}CAD"
    response = requests.get(
        VALET_OBSERVATIONS_URL.format(series=series),
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        headers=_HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    rows = []
    for observation in response.json().get("observations", []):
        value = observation.get(series, {}).get("v")
        if value is None:
            continue

        observation_date = date.fromisoformat(observation["d"])
        row = FxRate.query.filter_by(date=observation_date, pair=pair).first()
        if row is None:
            row = FxRate(date=observation_date, pair=pair, rate=float(value))
            db.session.add(row)
        else:
            row.rate = float(value)
        rows.append(row)

    return rows


def fx_rate_to_cad_on(currency: str, on_date: date) -> float | None:
    """Return the rate for a date, fetching it when absent.

    Weekends and Canadian banking holidays have no daily observation. In that
    case the latest published rate from the preceding seven days is used.
    """
    normalized_currency = currency.strip().upper()
    if normalized_currency == "CAD":
        return 1.0
    if normalized_currency not in _SERIES_BY_CURRENCY:
        return None

    pair = f"{normalized_currency}CAD"
    exact = FxRate.query.filter_by(date=on_date, pair=pair).first()
    if exact is not None:
        return exact.rate

    start_date = on_date - timedelta(days=_LOOKBACK_DAYS)
    try:
        fetch_rates_to_cad(normalized_currency, start_date, on_date)
    except (requests.RequestException, TypeError, ValueError, KeyError) as exc:
        current_app.logger.warning(
            "Could not fetch FX rate %s for %s: %s", pair, on_date.isoformat(), exc,
        )

    latest = (
        FxRate.query
        .filter(
            FxRate.pair == pair,
            FxRate.date >= start_date,
            FxRate.date <= on_date,
        )
        .order_by(FxRate.date.desc())
        .first()
    )
    return latest.rate if latest is not None else None


def latest_fx_rate_to_cad(currency: str) -> float | None:
    """Return the newest cached rate used for current portfolio valuation."""
    normalized_currency = currency.strip().upper()
    if normalized_currency == "CAD":
        return 1.0
    pair = f"{normalized_currency}CAD"
    row = FxRate.query.filter_by(pair=pair).order_by(FxRate.date.desc()).first()
    return row.rate if row is not None else None
