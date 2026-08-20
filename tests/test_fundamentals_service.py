from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.models import Asset, Fundamentals
from src.services import fundamentals as fundamentals_service
from src.services.fundamentals import (
    carry_forward_statements,
    derive_indicators,
    ensure_statement_metrics,
)


@pytest.fixture(autouse=True)
def _clear_fetch_guard():
    """The retry guard is keyed by asset id, and every test rebuilds the DB
    from id 1 — without this, one test's fetch suppresses the next one's."""
    fundamentals_service._statement_attempts.clear()
    yield
    fundamentals_service._statement_attempts.clear()


def _asset(db):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank')
    db.session.add(asset)
    db.session.commit()
    return asset


def _snapshot(db, asset, as_of=None, **values):
    snapshot = Fundamentals(asset_id=asset.id, as_of_date=as_of or date.today(), **values)
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


def _statement_values(**overrides):
    values = dict(
        revenue=1000.0, ebit=200.0, ebitda=300.0, total_assets=2000.0,
        total_liabilities=1200.0, total_equity=800.0, tax_rate=0.25,
    )
    values.update(overrides)
    return values


def test_derive_indicators_computes_ratios_from_market_and_statement_sides(db):
    snapshot = Fundamentals(
        market_cap=2400.0, enterprise_value=3000.0, net_debt=600.0, total_debt=700.0,
        **_statement_values(),
    )

    derive_indicators(snapshot)

    assert snapshot.p_ebit == 12.0                  # 2400 / 200
    assert snapshot.ev_ebit == 15.0                 # 3000 / 200
    assert snapshot.price_to_assets == 1.2          # 2400 / 2000
    assert snapshot.liabilities_to_assets == 0.6    # 1200 / 2000
    assert snapshot.asset_turnover == 0.5           # 1000 / 2000
    assert snapshot.net_debt_to_equity == 0.75      # 600 / 800
    assert snapshot.net_debt_to_ebitda == 2.0       # 600 / 300
    assert snapshot.roic == 0.1                     # 200 * (1 - .25) / (800 + 700)


def test_derive_indicators_skips_ratios_with_a_non_positive_denominator(db):
    """A loss-making EBIT would make P/EBIT look cheap instead of undefined."""
    snapshot = Fundamentals(market_cap=2400.0, **_statement_values(ebit=-50.0, total_equity=-10.0))

    derive_indicators(snapshot)

    assert snapshot.p_ebit is None
    assert snapshot.net_debt_to_equity is None


def test_net_cash_keeps_its_sign(db):
    """More cash than debt is a real, meaningful negative — not missing data."""
    snapshot = Fundamentals(net_debt=-400.0, **_statement_values())

    derive_indicators(snapshot)

    assert snapshot.net_debt_to_equity == -0.5


def test_roic_falls_back_to_a_default_tax_rate(db):
    snapshot = Fundamentals(total_debt=200.0, **_statement_values(tax_rate=None))

    derive_indicators(snapshot)

    expected = 200.0 * (1 - fundamentals_service.DEFAULT_TAX_RATE) / (800.0 + 200.0)
    assert snapshot.roic == expected


def test_roic_is_none_without_a_debt_figure(db):
    snapshot = Fundamentals(**_statement_values())

    derive_indicators(snapshot)

    assert snapshot.roic is None


def test_carry_forward_copies_statements_from_the_last_snapshot_that_has_them(db):
    asset = _asset(db)
    _snapshot(db, asset, as_of=date.today() - timedelta(days=30), **_statement_values())
    today = _snapshot(db, asset, market_cap=2400.0)

    assert carry_forward_statements(asset, today) is True
    assert today.total_assets == 2000.0
    assert today.tax_rate == 0.25


def test_carry_forward_ignores_statements_older_than_a_reporting_quarter(db):
    asset = _asset(db)
    stale = date.today() - timedelta(days=fundamentals_service.STATEMENT_MAX_AGE_DAYS + 1)
    _snapshot(db, asset, as_of=stale, **_statement_values())
    today = _snapshot(db, asset, market_cap=2400.0)

    assert carry_forward_statements(asset, today) is False
    assert today.total_assets is None


def test_carry_forward_leaves_a_snapshot_that_already_has_statements_alone(db):
    asset = _asset(db)
    _snapshot(db, asset, as_of=date.today() - timedelta(days=30), **_statement_values())
    today = _snapshot(db, asset, **_statement_values(total_assets=9999.0))

    assert carry_forward_statements(asset, today) is True
    assert today.total_assets == 9999.0


@patch('src.services.fundamentals.get_provider')
def test_ensure_statement_metrics_fetches_when_nothing_can_be_carried_forward(mock_get_provider, db):
    asset = _asset(db)
    provider = MagicMock()
    provider.get_statement_metrics.return_value = _statement_values()
    provider.get_fundamentals.return_value = {'market_cap': 2400.0, 'enterprise_value': 3000.0}
    mock_get_provider.return_value = provider
    snapshot = _snapshot(db, asset)

    ensure_statement_metrics(asset, snapshot)

    assert snapshot.total_assets == 2000.0
    assert snapshot.p_ebit == 12.0
    provider.get_statement_metrics.assert_called_once_with('RY.TO')


@patch('src.services.fundamentals.get_provider')
def test_ensure_statement_metrics_never_fetches_when_forbidden(mock_get_provider, db):
    """What the nightly job needs: it sweeps the whole universe, so it carries
    figures forward but never pays for two extra Yahoo calls per asset."""
    asset = _asset(db)
    snapshot = _snapshot(db, asset)

    ensure_statement_metrics(asset, snapshot, allow_fetch=False)

    mock_get_provider.assert_not_called()
    assert snapshot.total_assets is None


@patch('src.services.fundamentals.get_provider')
def test_ensure_statement_metrics_creates_todays_snapshot_when_there_is_none(mock_get_provider, db):
    asset = _asset(db)
    provider = MagicMock()
    provider.get_statement_metrics.return_value = _statement_values()
    provider.get_fundamentals.return_value = None
    mock_get_provider.return_value = provider

    snapshot = ensure_statement_metrics(asset, None)

    assert snapshot.as_of_date == date.today()
    assert snapshot.total_equity == 800.0


@patch('src.services.fundamentals.get_provider')
def test_ensure_statement_metrics_survives_a_failing_provider(mock_get_provider, db):
    asset = _asset(db)
    provider = MagicMock()
    provider.get_statement_metrics.side_effect = Exception('429 Too Many Requests')
    mock_get_provider.return_value = provider
    snapshot = _snapshot(db, asset, market_cap=2400.0)

    ensure_statement_metrics(asset, snapshot)

    assert snapshot.total_assets is None
    assert snapshot.market_cap == 2400.0


@patch('src.services.fundamentals.get_provider')
def test_info_refresh_only_fills_gaps(mock_get_provider, db):
    """The nightly snapshot stays the authority for anything it already wrote."""
    asset = _asset(db)
    provider = MagicMock()
    provider.get_statement_metrics.return_value = _statement_values()
    provider.get_fundamentals.return_value = {'market_cap': 9999.0, 'enterprise_value': 3000.0}
    mock_get_provider.return_value = provider
    snapshot = _snapshot(db, asset, market_cap=2400.0)

    ensure_statement_metrics(asset, snapshot)

    assert snapshot.market_cap == 2400.0
    assert snapshot.enterprise_value == 3000.0
