"""Phase 5 rankings computed from stored fundamentals and dividends."""

from collections import defaultdict
from datetime import date

from src.services.value_methods import canonical_sector


def _positive(value):
    return value is not None and value > 0


def top_dividend_yield(rows, limit=20):
    """Highest positive reported yield among active TSX companies."""
    eligible = [
        {"asset": asset, "fundamentals": fundamentals}
        for asset, fundamentals in rows
        if asset.exchange == "TSX"
        and fundamentals is not None
        and _positive(fundamentals.dividend_yield)
    ]
    eligible.sort(key=lambda row: row["fundamentals"].dividend_yield, reverse=True)
    for position, row in enumerate(eligible[:limit], start=1):
        row["rank"] = position
    return eligible[:limit]


def best_roe_by_sector(rows, per_sector=5):
    """Top positive ROE names inside each canonical sector."""
    grouped = defaultdict(list)
    for asset, fundamentals in rows:
        if fundamentals is None or not _positive(fundamentals.roe):
            continue
        grouped[canonical_sector(asset.sector)].append({
            "asset": asset,
            "fundamentals": fundamentals,
        })

    result = []
    for sector in sorted(grouped):
        ranked = sorted(
            grouped[sector],
            key=lambda row: row["fundamentals"].roe,
            reverse=True,
        )[:per_sector]
        for position, row in enumerate(ranked, start=1):
            row["rank"] = position
        result.append({"sector": sector, "rows": ranked})
    return result


def dividend_aristocrats(assets, dividends, today=None, minimum_increases=5):
    """Canadian companies with consecutive completed-year dividend growth.

    Five years "raising" requires six annual totals: every total after the
    first must exceed the previous one. The current partial year is excluded
    so a company is not rejected simply because only a few payments occurred.
    """
    today = today or date.today()
    last_completed_year = today.year - 1
    assets_by_id = {asset.id: asset for asset in assets if asset.exchange == "TSX"}
    annual = defaultdict(lambda: defaultdict(float))
    for dividend in dividends:
        if dividend.asset_id in assets_by_id and dividend.ex_date.year <= last_completed_year:
            annual[dividend.asset_id][dividend.ex_date.year] += dividend.amount

    result = []
    for asset_id, totals in annual.items():
        if last_completed_year not in totals:
            continue
        streak = 0
        year = last_completed_year
        while year - 1 in totals and totals[year] > totals[year - 1]:
            streak += 1
            year -= 1
        if streak >= minimum_increases:
            result.append({
                "asset": assets_by_id[asset_id],
                "streak": streak,
                "latest_annual_dividend": totals[last_completed_year],
                "latest_year": last_completed_year,
            })

    result.sort(key=lambda row: (-row["streak"], row["asset"].symbol))
    for position, row in enumerate(result, start=1):
        row["rank"] = position
    return result
