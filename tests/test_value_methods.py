from datetime import date

import pytest

from src.models import Asset, Fundamentals
from src.services.value_methods import rank_companies


def _company(db, symbol, sector, **fundamentals):
    asset = Asset(
        symbol=symbol,
        yahoo_symbol=symbol,
        exchange="US",
        currency="USD",
        name=f"{symbol} Corp",
        sector=sector,
    )
    db.session.add(asset)
    db.session.flush()
    snapshot = Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 20), **fundamentals)
    db.session.add(snapshot)
    db.session.commit()
    return asset, snapshot


def test_graham_formula_and_sector_ranking(db):
    _company(db, "CHEAP", "Technology", price=10, eps=2, book_value_per_share=8, pe=5, pb=1.25)
    _company(db, "RICH", "Technology", price=20, eps=2, book_value_per_share=8, pe=10, pb=2.5)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    groups = rank_companies(rows, "graham")

    assert [row["asset"].symbol for row in groups[0]["rows"]] == ["CHEAP", "RICH"]
    assert groups[0]["rows"][0]["fair_value"] == pytest.approx((22.5 * 2 * 8) ** 0.5)
    assert groups[0]["rows"][0]["sector_rank"] == 1


def test_graham_omits_losses_and_negative_book_value(db):
    _company(db, "LOSS", "Industrials", price=10, eps=-1, book_value_per_share=8)
    _company(db, "NEGBOOK", "Industrials", price=10, eps=1, book_value_per_share=-8)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    assert rank_companies(rows, "graham") == []


def test_graham_recovers_book_value_per_share_from_price_to_book(db):
    _company(db, "LEGACY", "Industrials", price=12, eps=2, pb=1.5)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    result = rank_companies(rows, "graham")[0]["rows"][0]

    assert result["fair_value"] == pytest.approx((22.5 * 2 * 8) ** 0.5)


def test_bazin_uses_six_percent_required_yield(db):
    _company(db, "DIV", "Utilities", price=20, dividend_rate=1.8, dividend_yield=0.09, payout_ratio=0.6)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    result = rank_companies(rows, "bazin")[0]["rows"][0]

    assert result["fair_value"] == pytest.approx(30)
    assert result["result"] == pytest.approx(0.5)


def test_greenblatt_combines_earnings_yield_and_roic_within_sector(db):
    _company(db, "BAL", "Industrials", price=10, ev_ebit=8, roic=0.20)
    _company(db, "WEAK", "Industrials", price=10, ev_ebit=16, roic=0.08)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    results = rank_companies(rows, "greenblatt")[0]["rows"]

    assert results[0]["asset"].symbol == "BAL"
    assert results[0]["result"] == 100
    assert results[1]["result"] == 0


def test_greenblatt_uses_explicitly_labelled_proxies_when_statements_are_missing(db):
    _company(db, "PROXY", "Technology", price=10, ev_ebitda=10, roa=0.12)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    result = rank_companies(rows, "greenblatt")[0]["rows"][0]

    assert result["metric_a"][0] == "EBITDA/EV · proxy"
    assert result["metric_b"][0] == "ROA · proxy"


def test_equivalent_sector_labels_share_one_peer_group(db):
    _company(db, "SOFT", "Information Technology", price=10, eps=2, pb=1.5)
    _company(db, "HARD", "Technology", price=12, eps=2, pb=1.5)
    rows = db.session.query(Asset, Fundamentals).join(Fundamentals).all()

    groups = rank_companies(rows, "graham")

    assert [group["sector"] for group in groups] == ["Technology"]
    assert len(groups[0]["rows"]) == 2


def test_value_methods_page_and_profile_entry_are_authenticated(auth_client, db):
    _company(db, "VALUE", "Financial Services", price=10, eps=2, book_value_per_share=8, pe=5, pb=1.25)

    response = auth_client.get("/tools/value-methods")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Análisis de acciones por grandes inversores" in body
    assert "Benjamin Graham" in body
    assert "Financial Services" in body
    assert "Herramientas" in body
    assert 'href="/tools/value-methods"' in body


def test_value_methods_page_filters_sector(auth_client, db):
    _company(db, "TECH", "Technology", price=10, eps=2, book_value_per_share=8)
    _company(db, "BANK", "Financial Services", price=10, eps=2, book_value_per_share=8)

    body = auth_client.get("/tools/value-methods?sector=Technology").get_data(as_text=True)

    assert "TECH Corp" in body
    assert "BANK Corp" not in body


def test_value_methods_page_requires_login(client):
    response = client.get("/tools/value-methods")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
