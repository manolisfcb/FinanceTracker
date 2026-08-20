from unittest.mock import Mock, patch

import pytest

from src.models import Asset, AssetCategory
from src.services.portfolio_analytics import (
    _boc_rate_cache,
    _canadian_policy_rate_return,
    classify_asset,
)


def test_asset_category_is_persisted_when_asset_is_created():
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
    bond = Asset(
        symbol='GOC2030', yahoo_symbol='GOC2030', exchange='OTC', currency='CAD',
        name='Government of Canada Bond 2030', sector='Fixed Income',
    )
    bond_etf = Asset(
        symbol='ZAG', yahoo_symbol='ZAG.TO', exchange='TSX', currency='CAD',
        name='BMO Aggregate Bond Index ETF', sector='ETFs', industry='Fixed Income',
    )
    fii = Asset(
        symbol='HGLG11', yahoo_symbol='HGLG11.SA', exchange='B3', currency='BRL',
        name='CSHG Logística FII', sector='Real Estate',
    )

    assert classify_asset(crypto) == AssetCategory.CRYPTO
    assert classify_asset(reit) == AssetCategory.REIT
    assert classify_asset(stock) == AssetCategory.EQUITY
    assert classify_asset(bond) == AssetCategory.FIXED_INCOME
    assert classify_asset(bond_etf) == AssetCategory.EQUITY
    assert classify_asset(fii) == AssetCategory.REIT


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
