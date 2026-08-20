from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from src.models import MarketIndicator
from src.services import market_strip

TORONTO = ZoneInfo("America/Toronto")


def _at(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=TORONTO)


class _Provider:
    """Stand-in for the market-data provider, keyed by Yahoo symbol."""

    def __init__(self, quotes, failing=()):
        self.quotes = quotes
        self.failing = set(failing)

    def get_quote(self, symbol):
        if symbol in self.failing:
            raise RuntimeError(f"provider down for {symbol}")
        return self.quotes.get(symbol)


# ── TSX session status ───────────────────────────────────────────────────

@pytest.mark.parametrize("moment, is_open", [
    (_at(2026, 8, 20, 11, 0), True),     # Thursday mid-session
    (_at(2026, 8, 20, 9, 29), False),    # one minute before the open
    (_at(2026, 8, 20, 9, 30), True),     # the open itself
    (_at(2026, 8, 20, 16, 0), False),    # the close is exclusive
    (_at(2026, 8, 22, 11, 0), False),    # Saturday
    (_at(2026, 7, 1, 11, 0), False),     # Canada Day
])
def test_tsx_session_open_state(moment, is_open):
    assert market_strip.tsx_session(moment)["is_open"] is is_open


def test_open_session_announces_the_close():
    assert "cierra 16:00 ET" in market_strip.tsx_session(_at(2026, 8, 20, 11))["text"]


def test_before_the_open_announces_todays_open():
    assert market_strip.tsx_session(_at(2026, 8, 20, 8))["text"] == "TSX cerrado · abre 9:30 ET"


def test_after_the_close_points_at_the_next_session():
    assert "mañana" in market_strip.tsx_session(_at(2026, 8, 20, 17))["text"]


def test_weekend_skips_to_monday():
    # Saturday: "mañana" would be Sunday, which is not a trading day.
    assert "el lunes" in market_strip.tsx_session(_at(2026, 8, 22, 11))["text"]


def test_the_day_before_a_holiday_skips_it():
    # 30 June 2026 is a Tuesday; 1 July is Canada Day, so the next open is
    # Thursday the 2nd — not "mañana".
    assert "el jueves" in market_strip.tsx_session(_at(2026, 6, 30, 17))["text"]


# ── Refreshing the indicators ────────────────────────────────────────────

def test_refresh_stores_indices_with_their_daily_change(app, db):
    provider = _Provider({
        "^GSPTSE": {"price": 25000.0, "previous_close": 24875.0},
        "^GSPC": {"price": 6000.0, "previous_close": 6000.0},
        "^IXIC": {"price": 20000.0, "previous_close": 20100.0},
    })

    with patch("src.services.market_strip.get_provider", return_value=provider), \
         patch("src.services.fx.latest_fx_rate_to_cad", return_value=None), \
         patch("src.services.market_strip.fetch_boc_policy_rate", return_value=None):
        assert market_strip.refresh_market_indicators() == 3
    db.session.commit()

    tsx = MarketIndicator.query.get("tsx")
    assert tsx.value == 25000.0
    assert tsx.change_percent == pytest.approx(0.5025, abs=1e-4)
    assert MarketIndicator.query.get("nasdaq").change_percent < 0


def test_refresh_overwrites_rather_than_appends(app, db):
    provider = _Provider({"^GSPTSE": {"price": 25000.0, "previous_close": 24875.0}})

    with patch("src.services.market_strip.get_provider", return_value=provider), \
         patch("src.services.fx.latest_fx_rate_to_cad", return_value=None), \
         patch("src.services.market_strip.fetch_boc_policy_rate", return_value=None):
        market_strip.refresh_market_indicators()
        db.session.commit()
        provider.quotes["^GSPTSE"] = {"price": 25500.0, "previous_close": 25000.0}
        market_strip.refresh_market_indicators()
        db.session.commit()

    assert MarketIndicator.query.filter_by(key="tsx").count() == 1
    assert MarketIndicator.query.get("tsx").value == 25500.0


def test_a_failing_index_does_not_cost_the_other_figures(app, db):
    """One dead Yahoo symbol must not empty the whole strip."""
    provider = _Provider(
        {"^GSPC": {"price": 6000.0, "previous_close": 5900.0}},
        failing=["^GSPTSE"],
    )

    with patch("src.services.market_strip.get_provider", return_value=provider), \
         patch("src.services.fx.latest_fx_rate_to_cad", return_value=1.3642), \
         patch("src.services.market_strip.fetch_boc_policy_rate", return_value=2.75):
        assert market_strip.refresh_market_indicators() == 3
    db.session.commit()

    assert MarketIndicator.query.get("tsx") is None
    assert MarketIndicator.query.get("usdcad").value == 1.3642
    assert MarketIndicator.query.get("boc_rate").value == 2.75


def test_a_failing_boc_call_leaves_the_rest_intact(app, db):
    provider = _Provider({"^GSPC": {"price": 6000.0, "previous_close": 5900.0}})

    with patch("src.services.market_strip.get_provider", return_value=provider), \
         patch("src.services.fx.latest_fx_rate_to_cad", return_value=1.36), \
         patch("src.services.market_strip.fetch_boc_policy_rate",
               side_effect=RuntimeError("valet down")):
        assert market_strip.refresh_market_indicators() == 2
    db.session.commit()

    assert MarketIndicator.query.get("boc_rate") is None
    assert MarketIndicator.query.get("sp500").value == 6000.0


def test_a_quote_without_a_previous_close_has_no_change(app, db):
    provider = _Provider({"^GSPTSE": {"price": 25000.0, "previous_close": None}})

    with patch("src.services.market_strip.get_provider", return_value=provider), \
         patch("src.services.fx.latest_fx_rate_to_cad", return_value=None), \
         patch("src.services.market_strip.fetch_boc_policy_rate", return_value=None):
        market_strip.refresh_market_indicators()
    db.session.commit()

    assert MarketIndicator.query.get("tsx").change_percent is None


# ── Rendering ────────────────────────────────────────────────────────────

def test_strip_renders_on_every_authenticated_page(auth_client, db):
    db.session.add(MarketIndicator(key="tsx", label="S&P/TSX", value=25000.0,
                                   change_percent=0.62, updated_at=datetime.utcnow()))
    db.session.add(MarketIndicator(key="usdcad", label="USD/CAD", value=1.3642,
                                   updated_at=datetime.utcnow()))
    db.session.add(MarketIndicator(key="boc_rate", label="Tasa BoC", value=2.75,
                                   updated_at=datetime.utcnow()))
    db.session.commit()

    body = auth_client.get("/community").get_data(as_text=True)

    assert "S&amp;P/TSX" in body
    assert "+0.62%" in body
    assert "1.3642" in body
    assert "2.75%" in body
    assert "TSX" in body
    assert 'role="region" aria-label="Resumen de mercados"' in body
    assert 'class="tn-market-track"' in body
    assert body.count('class="tn-market-group"') == 2
    assert 'aria-hidden="true"' in body
    assert "js/market_strip.js" in body


def test_strip_shows_unavailable_values_before_the_first_job_run(auth_client):
    body = auth_client.get("/community").get_data(as_text=True)
    assert "tn-market-strip" in body
    assert "S&amp;P/TSX" in body
    assert "S&amp;P 500" in body
    assert "NASDAQ" in body
    assert "USD/CAD" in body
    assert "Tasa BoC" in body
    assert "—" in body


def test_strip_renders_for_anonymous_visitors_too(client, db):
    """The landing page leads with the strip: index levels are public
    information, and it is the first signal that this is a markets tool."""
    db.session.add(MarketIndicator(key="tsx", label="S&P/TSX", value=25000.0,
                                   change_percent=0.62, updated_at=datetime.utcnow()))
    db.session.commit()

    body = client.get("/").get_data(as_text=True)

    assert "tn-market-strip" in body
    assert "S&amp;P/TSX" in body


def test_auth_layout_cannot_override_the_site_wide_strip(app):
    """The auth layout overrides chrome, while the ticker lives above it."""
    with app.test_request_context("/login"):
        context = {}
        app.update_template_context(context)
        body = app.jinja_env.get_template("auth_base.html").render(context)

    assert "tn-market-strip" in body
    assert "S&amp;P/TSX" in body
