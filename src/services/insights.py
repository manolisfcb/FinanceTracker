"""Sector-aware fundamental signals and an explainable quality score.

The result is deliberately computed from the latest Fundamentals snapshots
instead of persisted. A refreshed snapshot therefore changes the score
immediately and there is no second derived-data lifecycle to keep in sync.

Rules are data, not branches: changing a threshold or adding a sector
override only requires editing ``INDICATOR_RULES`` or
``SECTOR_RULE_OVERRIDES`` below. Values in Fundamentals use decimal fractions
for percentages (0.15 = 15%), except Yahoo's ``debt_to_equity``, which is in
percentage points (150 = 1.5x).
"""

from dataclasses import dataclass, replace
from math import isfinite
from statistics import median

from sqlalchemy import and_, func

from src.extensions import db
from src.models import Asset, Fundamentals


@dataclass(frozen=True)
class IndicatorRule:
    component: str
    direction: str
    green: float
    red: float
    sector_median: bool = False
    positive_only: bool = False


COMPONENTS = {
    "valuation": {"label": "Valuación", "weight": 0.25},
    "profitability": {"label": "Rentabilidad", "weight": 0.30},
    "debt": {"label": "Solidez", "weight": 0.25},
    "dividends": {"label": "Dividendos", "weight": 0.20},
}

# ``green`` is the good boundary and ``red`` the bad boundary. The order is
# naturally reversed for higher-is-better metrics.
INDICATOR_RULES = {
    # Valuation uses sector medians when at least three comparable snapshots
    # exist; absolute boundaries are a transparent fallback for sparse data.
    "pe": IndicatorRule("valuation", "lower", 15.0, 30.0, True, True),
    "forward_pe": IndicatorRule("valuation", "lower", 15.0, 30.0, True, True),
    "pb": IndicatorRule("valuation", "lower", 2.0, 5.0, True, True),
    "ps": IndicatorRule("valuation", "lower", 2.5, 7.0, True, True),
    "p_ebit": IndicatorRule("valuation", "lower", 12.0, 25.0, True, True),
    "ev_ebitda": IndicatorRule("valuation", "lower", 10.0, 20.0, True, True),
    # Profitability / growth.
    "roe": IndicatorRule("profitability", "higher", 0.15, 0.05),
    "roa": IndicatorRule("profitability", "higher", 0.07, 0.02),
    "roic": IndicatorRule("profitability", "higher", 0.12, 0.04),
    "operating_margin": IndicatorRule("profitability", "higher", 0.15, 0.05, True),
    "net_margin": IndicatorRule("profitability", "higher", 0.10, 0.02, True),
    "revenue_cagr": IndicatorRule("profitability", "higher", 0.08, 0.00),
    # Balance-sheet resilience.
    "net_debt_to_ebitda": IndicatorRule("debt", "lower", 2.0, 4.0),
    "debt_to_equity": IndicatorRule("debt", "lower", 100.0, 200.0),
    "liabilities_to_assets": IndicatorRule("debt", "lower", 0.55, 0.80),
    "current_ratio": IndicatorRule("debt", "higher", 1.50, 1.00),
    "quick_ratio": IndicatorRule("debt", "higher", 1.00, 0.70),
    # Income quality. A missing payout remains unavailable; zero is not
    # manufactured for companies that do not pay dividends.
    "dividend_yield": IndicatorRule("dividends", "higher", 0.03, 0.01),
    "payout_ratio": IndicatorRule("dividends", "lower", 0.70, 1.00),
}

# Sector-specific exceptions for economics that do not compare sensibly with
# a generic industrial company. Any field omitted keeps the default rule.
SECTOR_RULE_OVERRIDES = {
    "Financial Services": {
        "pb": {"green": 1.5, "red": 3.0, "sector_median": False},
        "roe": {"green": 0.12, "red": 0.05},
        "debt_to_equity": {"green": 200.0, "red": 500.0},
        "liabilities_to_assets": {"green": 0.85, "red": 0.95},
    },
    "Real Estate": {
        "net_debt_to_ebitda": {"green": 6.0, "red": 10.0},
        "payout_ratio": {"green": 0.90, "red": 1.10},
    },
    "Utilities": {
        "net_debt_to_ebitda": {"green": 4.0, "red": 6.0},
        "payout_ratio": {"green": 0.80, "red": 1.00},
    },
    "Technology": {
        "ps": {"green": 5.0, "red": 12.0, "sector_median": False},
        "revenue_cagr": {"green": 0.12, "red": 0.02},
    },
}

MIN_SECTOR_SAMPLE = 3
STATUS_SCORES = {"green": 100.0, "yellow": 55.0, "red": 15.0}
STATUS_LABELS = {"green": "Favorable", "yellow": "Neutral", "red": "Atención"}
PERCENT_INDICATORS = {
    "roe", "roa", "roic", "operating_margin", "net_margin", "revenue_cagr",
    "liabilities_to_assets", "dividend_yield", "payout_ratio",
}


def _number(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _rule_for(key: str, sector: str | None) -> IndicatorRule:
    rule = INDICATOR_RULES[key]
    changes = SECTOR_RULE_OVERRIDES.get(sector or "", {}).get(key)
    return replace(rule, **changes) if changes else rule


def _latest_sector_snapshots(sector: str | None):
    if not sector:
        return []
    latest = (
        db.session.query(
            Fundamentals.asset_id.label("asset_id"),
            func.max(Fundamentals.as_of_date).label("max_date"),
        )
        .group_by(Fundamentals.asset_id)
        .subquery()
    )
    return (
        db.session.query(Fundamentals)
        .join(Asset, Asset.id == Fundamentals.asset_id)
        .join(
            latest,
            and_(
                latest.c.asset_id == Fundamentals.asset_id,
                latest.c.max_date == Fundamentals.as_of_date,
            ),
        )
        .filter(Asset.sector == sector)
        .all()
    )


def sector_benchmarks(sector: str | None) -> dict[str, dict]:
    """Median and sample size for every median-backed indicator."""
    snapshots = _latest_sector_snapshots(sector)
    result = {}
    for key, base_rule in INDICATOR_RULES.items():
        rule = _rule_for(key, sector)
        if not rule.sector_median:
            continue
        values = []
        for snapshot in snapshots:
            value = _number(getattr(snapshot, key, None))
            if value is not None and (not base_rule.positive_only or value > 0):
                values.append(value)
        if len(values) >= MIN_SECTOR_SAMPLE:
            result[key] = {"median": median(values), "sample_size": len(values)}
    return result


def _effective_boundaries(rule: IndicatorRule, benchmark: dict | None):
    if not benchmark:
        return rule.green, rule.red, "regla sectorial" if not rule.sector_median else "regla general"
    sector_median = benchmark["median"]
    if rule.direction == "lower":
        return sector_median, sector_median * 1.5, f"mediana sector (n={benchmark['sample_size']})"
    return sector_median, sector_median * 0.7, f"mediana sector (n={benchmark['sample_size']})"


def _format_boundary(key: str, value: float) -> str:
    if key in PERCENT_INDICATORS:
        return f"{value * 100:.2f}%"
    return f"{value:.2f}"


def assess_indicator(
    key: str,
    value,
    sector: str | None = None,
    benchmark: dict | None = None,
) -> dict:
    """Apply one declarative traffic-light rule and explain its boundaries."""
    rule = _rule_for(key, sector)
    number = _number(value)
    if number is None or (rule.positive_only and number <= 0):
        return {
            "status": "unavailable",
            "label": "Sin datos",
            "score": None,
            "explanation": "No hay un valor comparable para calificar.",
        }

    green, red, source = _effective_boundaries(rule, benchmark)
    if rule.direction == "lower":
        status = "green" if number <= green else "red" if number >= red else "yellow"
        boundaries = (
            f"favorable ≤ {_format_boundary(key, green)}; "
            f"atención ≥ {_format_boundary(key, red)}"
        )
    else:
        status = "green" if number >= green else "red" if number <= red else "yellow"
        boundaries = (
            f"favorable ≥ {_format_boundary(key, green)}; "
            f"atención ≤ {_format_boundary(key, red)}"
        )

    return {
        "status": status,
        "label": STATUS_LABELS[status],
        "score": STATUS_SCORES[status],
        "explanation": f"{boundaries} ({source}).",
    }


def build_company_insight(asset, fundamentals) -> dict:
    """Return traffic lights, four component scores and a weighted 0–100.

    Missing indicators are excluded rather than treated as zero. ``coverage``
    makes the resulting uncertainty visible to the user.
    """
    benchmarks = sector_benchmarks(asset.sector)
    assessments = {
        key: assess_indicator(
            key,
            getattr(fundamentals, key, None) if fundamentals else None,
            asset.sector,
            benchmarks.get(key),
        )
        for key in INDICATOR_RULES
    }

    components = []
    weighted_total = 0.0
    available_weight = 0.0
    available_indicators = 0
    for component_key, config in COMPONENTS.items():
        members = [
            assessment for key, assessment in assessments.items()
            if INDICATOR_RULES[key].component == component_key
        ]
        scores = [item["score"] for item in members if item["score"] is not None]
        score = round(sum(scores) / len(scores)) if scores else None
        status_counts = {
            status: sum(item["status"] == status for item in members)
            for status in ("green", "yellow", "red")
        }
        if score is not None:
            weighted_total += score * config["weight"]
            available_weight += config["weight"]
            available_indicators += len(scores)
        components.append({
            "key": component_key,
            "label": config["label"],
            "score": score,
            "available": len(scores),
            "total": len(members),
            "weight": int(config["weight"] * 100),
            "explanation": (
                f"{status_counts['green']} favorables, {status_counts['yellow']} neutrales y "
                f"{status_counts['red']} en atención."
                if scores else "Sin indicadores suficientes para calificar."
            ),
        })

    score = round(weighted_total / available_weight) if available_weight else None
    total_indicators = len(assessments)
    coverage = round(available_indicators / total_indicators * 100) if total_indicators else 0
    if score is None:
        label, status = "Sin calificar", "unavailable"
    elif score >= 75:
        label, status = "Calidad fuerte", "green"
    elif score >= 55:
        label, status = "Calidad intermedia", "yellow"
    else:
        label, status = "Calidad débil", "red"

    return {
        "score": score,
        "label": label,
        "status": status,
        "coverage": coverage,
        "available_indicators": available_indicators,
        "total_indicators": total_indicators,
        "components": components,
        "indicators": assessments,
        "sector": asset.sector or "Sin sector",
    }
