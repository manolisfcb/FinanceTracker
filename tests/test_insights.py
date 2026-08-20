from datetime import date, timedelta
from types import SimpleNamespace

from src.models import Asset, Fundamentals
from src.services.insights import (
    INDICATOR_RULES,
    assess_indicator,
    build_company_insight,
    sector_benchmarks,
)


def _asset(db, symbol, sector="Industrials"):
    asset = Asset(
        symbol=symbol,
        yahoo_symbol=f"{symbol}.TO",
        exchange="TSX",
        currency="CAD",
        name=f"{symbol} Inc.",
        sector=sector,
    )
    db.session.add(asset)
    db.session.flush()
    return asset


def test_lower_is_better_rule_uses_sector_median():
    assessment = assess_indicator(
        "pe", 12.0, "Industrials", {"median": 15.0, "sample_size": 8}
    )

    assert assessment["status"] == "green"
    assert assessment["score"] == 100
    assert "mediana sector (n=8)" in assessment["explanation"]


def test_sector_override_changes_debt_boundary_for_financials():
    generic = assess_indicator("debt_to_equity", 300.0, "Industrials")
    financial = assess_indicator("debt_to_equity", 300.0, "Financial Services")

    assert generic["status"] == "red"
    assert financial["status"] == "yellow"
    assert "regla sectorial" in financial["explanation"]


def test_non_positive_valuation_multiple_is_unavailable():
    assessment = assess_indicator("pe", -8.0, "Technology")

    assert assessment["status"] == "unavailable"
    assert assessment["score"] is None


def test_sector_benchmark_uses_only_each_assets_latest_snapshot(db):
    today = date.today()
    for index, pe in enumerate((10.0, 20.0, 30.0), start=1):
        asset = _asset(db, f"I{index}")
        db.session.add_all([
            Fundamentals(asset_id=asset.id, as_of_date=today - timedelta(days=1), pe=999.0),
            Fundamentals(asset_id=asset.id, as_of_date=today, pe=pe),
        ])
    db.session.commit()

    benchmark = sector_benchmarks("Industrials")["pe"]

    assert benchmark == {"median": 20.0, "sample_size": 3}


def test_quality_score_is_weighted_and_fully_explained(db):
    asset = _asset(db, "GOOD", sector=None)
    values = {}
    for key, rule in INDICATOR_RULES.items():
        values[key] = rule.green
    fundamentals = SimpleNamespace(**values)

    insight = build_company_insight(asset, fundamentals)

    assert insight["score"] == 100
    assert insight["label"] == "Calidad fuerte"
    assert insight["coverage"] == 100
    assert sum(component["weight"] for component in insight["components"]) == 100
    assert all(component["score"] == 100 for component in insight["components"])
    assert all("favorables" in component["explanation"] for component in insight["components"])


def test_missing_data_is_not_scored_as_zero(db):
    asset = _asset(db, "EMPTY", sector=None)

    insight = build_company_insight(asset, SimpleNamespace())

    assert insight["score"] is None
    assert insight["coverage"] == 0
    assert insight["status"] == "unavailable"
    assert all(component["score"] is None for component in insight["components"])
