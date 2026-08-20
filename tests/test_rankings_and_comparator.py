from datetime import date
from unittest.mock import patch

import pytest

from src.models import Asset, DividendHistory, Fundamentals
from src.services.comparator import build_comparison, normalize_price_history
from src.services.rankings import best_roe_by_sector, dividend_aristocrats, top_dividend_yield


def _company(db, symbol, exchange="TSX", sector="Technology", **fundamentals):
    asset = Asset(
        symbol=symbol,
        yahoo_symbol=f"{symbol}.TO" if exchange == "TSX" else symbol,
        exchange=exchange,
        currency="CAD" if exchange == "TSX" else "USD",
        name=f"{symbol} Corp",
        sector=sector,
    )
    db.session.add(asset)
    db.session.flush()
    snapshot = Fundamentals(
        asset_id=asset.id,
        as_of_date=date(2026, 8, 20),
        **fundamentals,
    )
    db.session.add(snapshot)
    db.session.commit()
    return asset, snapshot


def _annual_dividends(db, asset, totals):
    for year, amount in totals.items():
        db.session.add(DividendHistory(
            asset_id=asset.id,
            ex_date=date(year, 12, 15),
            amount=amount,
            currency=asset.currency,
        ))
    db.session.commit()


def test_dividend_yield_ranking_is_tsx_only_and_descending(db):
    high = _company(db, "HIGH", dividend_yield=0.08)[0]
    low = _company(db, "LOW", dividend_yield=0.03)[0]
    _company(db, "USCO", exchange="US", dividend_yield=0.20)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    ranking = top_dividend_yield(rows)

    assert [row["asset"] for row in ranking] == [high, low]
    assert [row["rank"] for row in ranking] == [1, 2]


def test_aristocrat_requires_five_completed_year_increases(db):
    growing = _company(db, "GROW")[0]
    flat = _company(db, "FLAT")[0]
    _annual_dividends(db, growing, {2020: 1.0, 2021: 1.1, 2022: 1.2, 2023: 1.3, 2024: 1.4, 2025: 1.5})
    _annual_dividends(db, flat, {2020: 1.0, 2021: 1.1, 2022: 1.2, 2023: 1.2, 2024: 1.4, 2025: 1.5})

    ranking = dividend_aristocrats(
        [growing, flat], DividendHistory.query.all(), today=date(2026, 8, 20)
    )

    assert len(ranking) == 1
    assert ranking[0]["asset"] == growing
    assert ranking[0]["streak"] == 5


def test_best_roe_groups_equivalent_sector_labels(db):
    _company(db, "A", sector="Information Technology", roe=0.25)
    _company(db, "B", sector="Technology", roe=0.15)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    groups = best_roe_by_sector(rows)

    assert [group["sector"] for group in groups] == ["Technology"]
    assert [row["asset"].symbol for row in groups[0]["rows"]] == ["A", "B"]


def test_comparison_ranks_lower_and_higher_metrics_in_the_right_direction(db):
    cheap = _company(db, "CHEAP", pe=10, roe=0.12)[0]
    quality = _company(db, "QUALITY", pe=20, roe=0.25)[0]
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).filter(Asset.id.in_([cheap.id, quality.id])).all()

    comparison = build_comparison(rows)
    metrics = {
        metric["key"]: metric
        for group in comparison["groups"]
        for metric in group["metrics"]
    }

    assert [cell["rank"] for cell in metrics["pe"]["cells"]] == [1, 2]
    assert [cell["rank"] for cell in metrics["roe"]["cells"]] == [2, 1]
    assert [column["overall_rank"] for column in comparison["columns"]] == [2, 1]


def test_price_history_is_normalized_to_first_close():
    points = normalize_price_history([
        {"date": "2026-08-18", "close": 100},
        {"date": "2026-08-19", "close": 110},
        {"date": "2026-08-20", "close": 90},
    ])

    assert [point["value"] for point in points] == pytest.approx([0, 10, -10])


def test_rankings_and_comparator_pages_render(auth_client, db):
    first = _company(db, "RY", sector="Financial Services", market_cap=10_000, price=100, roe=0.18, dividend_yield=0.04)[0]
    second = _company(db, "TD", sector="Financial Services", market_cap=9_000, price=80, roe=0.15, dividend_yield=0.05)[0]

    rankings = auth_client.get("/tools/rankings")
    comparator = auth_client.get(f"/tools/comparator?asset={first.id}&asset={second.id}")

    assert rankings.status_code == 200
    assert "Mayor dividend yield" in rankings.get_data(as_text=True)
    assert "Mejor ROE por sector" in rankings.get_data(as_text=True)
    assert comparator.status_code == 200
    body = comparator.get_data(as_text=True)
    assert "Comparador de acciones" in body
    assert "Rentabilidad comparada" in body
    assert "P/L" in body
    assert "RY Corp" in body and "TD Corp" in body


def test_comparator_opens_empty_until_user_selects_companies(auth_client, db):
    _company(db, "BIG", market_cap=999_000, price=100)

    body = auth_client.get("/tools/comparator").get_data(as_text=True)

    assert "Empezá por la primera empresa" in body
    assert "No elegimos acciones por vos" in body
    assert "BIG Corp" not in body


def test_comparator_keeps_selected_asset_without_fundamentals(auth_client, db):
    complete = _company(db, "DATA", market_cap=100, price=10)[0]
    pending = Asset(
        symbol="PENDING", yahoo_symbol="PENDING.TO", exchange="TSX", currency="CAD",
        name="Pending Corp", sector="Industrials",
    )
    db.session.add(pending)
    db.session.commit()

    body = auth_client.get(
        f"/tools/comparator?asset={complete.id}&asset={pending.id}"
    ).get_data(as_text=True)

    assert "Pending Corp" in body
    assert "—º" in body


@patch("src.routes.tools.get_provider")
def test_comparator_price_api_returns_normalized_series(mock_provider, auth_client, db):
    asset = _company(db, "RY", price=100)[0]
    mock_provider.return_value.get_price_history.return_value = [
        {"date": "2026-08-19", "close": 100},
        {"date": "2026-08-20", "close": 125},
    ]

    response = auth_client.get(f"/api/tools/comparator/prices?asset={asset.id}&range=1Y")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["range"] == "1Y"
    assert payload["series"][0]["ending_return"] == 25
    mock_provider.return_value.get_price_history.assert_called_once_with("RY.TO", "1Y")


def test_new_tools_require_login(client):
    assert client.get("/tools/rankings").status_code == 302
    assert client.get("/tools/comparator").status_code == 302
    assert client.get("/api/tools/comparator/prices?asset=1").status_code == 302
