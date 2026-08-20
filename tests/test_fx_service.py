from datetime import date
from unittest.mock import MagicMock, patch

import requests

from src.models import FxRate
from src.services.fx import fx_rate_to_cad_on


@patch('src.services.fx.requests.get')
def test_fx_lookup_fetches_and_caches_the_rate_for_the_order_date(mock_get, db):
    mock_get.return_value = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={
            'observations': [
                {'d': '2026-08-20', 'FXUSDCAD': {'v': '1.3875'}},
            ],
        }),
    )

    rate = fx_rate_to_cad_on('USD', date(2026, 8, 20))

    assert rate == 1.3875
    row = FxRate.query.filter_by(date=date(2026, 8, 20), pair='USDCAD').one()
    assert row.rate == 1.3875
    assert mock_get.call_args.kwargs['params'] == {
        'start_date': '2026-08-13',
        'end_date': '2026-08-20',
    }


@patch('src.services.fx.requests.get')
def test_fx_lookup_uses_previous_business_day_on_a_weekend(mock_get, db):
    mock_get.return_value = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={
            'observations': [
                {'d': '2026-08-14', 'FXUSDCAD': {'v': '1.39'}},
            ],
        }),
    )

    assert fx_rate_to_cad_on('USD', date(2026, 8, 16)) == 1.39


@patch('src.services.fx.requests.get')
def test_fx_lookup_does_not_call_bank_when_the_exact_rate_is_cached(mock_get, db):
    db.session.add(FxRate(date=date(2026, 8, 20), pair='USDCAD', rate=1.40))
    db.session.commit()

    assert fx_rate_to_cad_on('USD', date(2026, 8, 20)) == 1.40
    mock_get.assert_not_called()


@patch('src.services.fx.requests.get')
def test_fx_lookup_returns_none_when_bank_and_cache_are_unavailable(mock_get, db):
    mock_get.side_effect = requests.ConnectionError('offline')

    assert fx_rate_to_cad_on('USD', date(2026, 8, 20)) is None
