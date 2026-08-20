"""Statement-derived indicators for the company page.

`refresh_fundamentals` fills each day's Fundamentals snapshot from Yahoo's
`info` payload — one request per asset, cheap enough to sweep the whole
universe nightly. The balance-sheet and income-statement figures behind
P/EBIT, ROIC, deuda neta/EBITDA and giro del activo sit behind two slower
endpoints and only move when a company reports, so they're filled here
instead: carried forward from the last snapshot that has them, and fetched
only when no recent snapshot does.
"""
import time
from datetime import date, timedelta

from src.extensions import db
from src.models import Fundamentals
from src.resources.jobs._common import get_or_create_snapshot
from src.services.market_data import get_provider

# Figures read straight off the statements — copied forward between daily
# snapshots until the company reports again.
STATEMENT_FIELDS = (
    'revenue',
    'ebit',
    'ebitda',
    'total_assets',
    'total_liabilities',
    'total_equity',
    'tax_rate',
    'revenue_cagr',
    'revenue_cagr_years',
)

# How stale a carried-forward balance sheet may get. Companies report
# quarterly, so a bit over a quarter forces a re-fetch shortly after results.
STATEMENT_MAX_AGE_DAYS = 100

# How long before a fetch is retried for an asset whose statements came back
# empty — same bound as the company-page backfill, for the same reason.
STATEMENT_RETRY_SECONDS = 6 * 3600

# Effective tax rate for ROIC when the income statement doesn't report one.
DEFAULT_TAX_RATE = 0.25
# Beyond this, a reported rate is a one-off distortion (a settlement, a
# write-off) rather than the company's real tax burden.
MAX_TAX_RATE = 0.6

_statement_attempts: dict[int, float] = {}


def _ratio(numerator, denominator):
    """None unless both sides are present and the denominator is positive.

    A non-positive denominator (equity wiped out by losses, a loss-making
    EBIT) makes these ratios meaningless rather than negative — P/EBIT of -8
    would read as "cheap" — so those return None and the page shows an em
    dash. Negative numerators are fine and meaningful (net cash, a negative
    ROIC).
    """
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def derive_indicators(snapshot) -> None:
    """Recompute every ratio that combines market data with statement figures.

    Always recomputed rather than stored by the fetcher: the market side
    (price, market cap, EV) moves daily while the statement side doesn't, so
    a stored ratio would go stale against its own inputs.
    """
    snapshot.p_ebit = _ratio(snapshot.market_cap, snapshot.ebit)
    snapshot.ev_ebit = _ratio(snapshot.enterprise_value, snapshot.ebit)
    snapshot.price_to_assets = _ratio(snapshot.market_cap, snapshot.total_assets)
    snapshot.liabilities_to_assets = _ratio(snapshot.total_liabilities, snapshot.total_assets)
    snapshot.asset_turnover = _ratio(snapshot.revenue, snapshot.total_assets)
    snapshot.net_debt_to_equity = _ratio(snapshot.net_debt, snapshot.total_equity)
    snapshot.net_debt_to_ebitda = _ratio(snapshot.net_debt, snapshot.ebitda)
    snapshot.roic = _roic(snapshot)


def _roic(snapshot):
    """NOPAT / capital invertido. yfinance's `info` exposes ROE and ROA but
    no ROIC, so it's built from EBIT after tax over patrimonio + deuda bruta.
    """
    if snapshot.ebit is None or snapshot.total_equity is None or snapshot.total_debt is None:
        return None
    tax_rate = snapshot.tax_rate if snapshot.tax_rate is not None else DEFAULT_TAX_RATE
    tax_rate = min(max(tax_rate, 0.0), MAX_TAX_RATE)
    return _ratio(snapshot.ebit * (1 - tax_rate), snapshot.total_equity + snapshot.total_debt)


def _carry_forward_source(asset_id: int, exclude_id):
    """Most recent snapshot still holding usable statement figures."""
    query = Fundamentals.query.filter(
        Fundamentals.asset_id == asset_id,
        Fundamentals.total_assets.isnot(None),
        Fundamentals.as_of_date >= date.today() - timedelta(days=STATEMENT_MAX_AGE_DAYS),
    )
    if exclude_id is not None:
        query = query.filter(Fundamentals.id != exclude_id)
    return query.order_by(Fundamentals.as_of_date.desc()).first()


def carry_forward_statements(asset, snapshot) -> bool:
    """Copy statement figures onto `snapshot` from the last snapshot that has
    them. Returns whether anything was copied — a caller that needs the
    figures can fall back to fetching when this comes back False.

    Doesn't commit, so the nightly job stays one all-or-nothing transaction.
    """
    if snapshot.total_assets is not None:
        return True
    source = _carry_forward_source(asset.id, snapshot.id)
    if source is None:
        return False
    for field in STATEMENT_FIELDS:
        setattr(snapshot, field, getattr(source, field))
    return True


def _fetch_statement_metrics(asset):
    """One capped, unthrottled attempt — same trade-off as the page's live
    quote: a slow Yahoo response must not stall the company page."""
    last_attempt = _statement_attempts.get(asset.id)
    if last_attempt and (time.monotonic() - last_attempt) < STATEMENT_RETRY_SECONDS:
        return None
    _statement_attempts[asset.id] = time.monotonic()

    provider = get_provider(max_retries=1, min_interval_seconds=0)
    try:
        return provider.get_statement_metrics(asset.yahoo_symbol)
    except Exception as exc:
        print(f"[fundamentals] statement fetch failed for {asset.symbol}: {exc}")
        return None


def _needs_info_refresh(snapshot) -> bool:
    """Whether the snapshot is missing the `info` figures the new indicators
    need. True for rows written before this feature existed, and for rows
    created by the intraday quote job, which only writes price."""
    return snapshot.book_value_per_share is None and snapshot.enterprise_value is None


def ensure_statement_metrics(asset, snapshot=None, allow_fetch: bool = True):
    """Fill `snapshot` with statement figures and recompute the ratios.

    Returns the snapshot that was filled, creating today's if `snapshot` is
    None. Never raises: a company with no statement data still renders, it
    just shows em dashes. Pass `allow_fetch=False` to carry forward without
    ever hitting the network — what the nightly job wants, since it sweeps
    the whole universe.
    """
    target = snapshot if snapshot is not None else get_or_create_snapshot(asset.id)

    try:
        if not carry_forward_statements(asset, target) and allow_fetch:
            metrics = _fetch_statement_metrics(asset)
            if metrics:
                for field in STATEMENT_FIELDS:
                    setattr(target, field, metrics.get(field))

        if allow_fetch and _needs_info_refresh(target):
            _refresh_info_figures(asset, target)

        derive_indicators(target)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        print(f"[fundamentals] ensure_statement_metrics failed for {asset.symbol}: {exc}")
    return target


def _refresh_info_figures(asset, snapshot) -> None:
    """Top up the `info`-sourced figures (market cap, EV, deuda, VPA) on a
    snapshot the nightly job hasn't written yet — several derived ratios have
    a market-side input that lives there, not in the statements."""
    provider = get_provider(max_retries=1, min_interval_seconds=0)
    try:
        data = provider.get_fundamentals(asset.yahoo_symbol)
    except Exception as exc:
        print(f"[fundamentals] info refresh failed for {asset.symbol}: {exc}")
        return
    if not data:
        return
    for key, value in data.items():
        # Only fills gaps: the nightly snapshot is the authority for anything
        # it already wrote, including today's price.
        if value is not None and getattr(snapshot, key, None) is None:
            setattr(snapshot, key, value)
