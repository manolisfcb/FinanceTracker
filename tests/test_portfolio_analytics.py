from unittest.mock import Mock, patch

import pytest

from src.models import Asset
from src.services.portfolio_analytics import (
    _boc_rate_cache,
    _canadian_policy_rate_return,
    classify_asset,
)


def test_asset_classification_uses_catalog_metadata():
    crypto = Asset(
        symbol='BTC', yahoo_symbol='BTC-CAD', exchange='CRYPTO', currency='CAD',
        name='Bitcoin', sector='Cryptoassets', industry='Cryptocurrency',
    )
    reit = Asset(
        symbol='O', yahoo_symbol='O', exchange='US', currency='USD',
        name='Realty Income', sector='Real Estate', industry='REIT - Retail',
    )
    stock = Asset(
        symbol='GOOGL', yahoo_symbol='GOOGL', exchange='US', currency='USD',
        name='Alphabet', sector='Communication Services', industry='Internet Content',
    )

    assert classify_asset(crypto) == 'CRYPTO'
    assert classify_asset(reit) == 'REIT'
    assert classify_asset(stock) == 'EQUITY_ETF'


@patch('src.services.portfolio_analytics.requests.get')
def test_policy_rate_is_compounded_into_a_comparable_return(mock_get):
    _boc_rate_cache.clear()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        'observations': [
            {'d': '2026-01-01', 'V39079': {'v': '3.65'}},
            {'d': '2026-01-11', 'V39079': {'v': '3.65'}},
        ]
    }
    mock_get.return_value = response

    result = _canadian_policy_rate_return('2026-01-01')

    assert result['2026-01-01'] == 0.0
    assert result['2026-01-11'] == pytest.approx(
        ((1 + 0.0365 / 365) ** 10 - 1) * 100
    )
    mock_get.assert_called_once()
