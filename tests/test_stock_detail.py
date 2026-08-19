from datetime import date
from unittest.mock import patch

from src.models import Asset, DividendHistory, Fundamentals


def _seed_asset(db, **overrides):
    defaults = dict(
        symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD',
        name='Royal Bank', sector='Financial Services', industry='Banks',
        website='https://www.rbc.com', ir_website='https://www.rbc.com/investors',
        description='A diversified Canadian financial institution.',
    )
    defaults.update(overrides)
    asset = Asset(**defaults)
    db.session.add(asset)
    db.session.commit()
    return asset


def test_stock_detail_404_for_unknown_symbol(auth_client, db):
    resp = auth_client.get('/stocks/TSX/NOPE')
    assert resp.status_code == 404


@patch('src.routes.stockViews.get_provider')
def test_stock_detail_renders_asset_info(mock_get_provider, auth_client, db):
    mock_get_provider.return_value.get_quote.return_value = None
    asset = _seed_asset(db)
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 19), pe=12.0, price=145.2))
    db.session.commit()

    resp = auth_client.get('/stocks/TSX/RY')

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Royal Bank' in body
    assert 'A diversified Canadian financial institution.' in body
    assert 'IR site' in body


@patch('src.routes.stockViews.get_provider')
def test_stock_detail_shows_day_change_from_live_quote(mock_get_provider, auth_client, db):
    mock_get_provider.return_value.get_quote.return_value = {
        'price': 150.0, 'previous_close': 145.0, 'currency': 'CAD',
    }
    _seed_asset(db)

    body = auth_client.get('/stocks/TSX/RY').get_data(as_text=True)

    assert '150.00' in body


@patch('src.routes.stockViews.get_provider')
def test_stock_detail_falls_back_to_stored_price_when_quote_unavailable(mock_get_provider, auth_client, db):
    mock_get_provider.return_value.get_quote.side_effect = Exception("429")
    asset = _seed_asset(db)
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 19), price=99.5))
    db.session.commit()

    body = auth_client.get('/stocks/TSX/RY').get_data(as_text=True)

    assert '99.50' in body


def test_stock_detail_shows_empty_state_without_dividends(auth_client, db):
    _seed_asset(db)
    body = auth_client.get('/stocks/TSX/RY').get_data(as_text=True)
    assert 'Sin historial de dividendos registrado.' in body


def test_stock_detail_lists_dividend_history(auth_client, db):
    asset = _seed_asset(db)
    db.session.add(DividendHistory(asset_id=asset.id, ex_date=date(2026, 3, 1), amount=0.5, currency='CAD'))
    db.session.commit()

    body = auth_client.get('/stocks/TSX/RY').get_data(as_text=True)

    assert '2026-03-01' in body
    assert 'Sin historial de dividendos registrado.' not in body


@patch('src.routes.stockViews.get_provider')
def test_asset_prices_endpoint_returns_json(mock_get_provider, auth_client, db):
    mock_get_provider.return_value.get_price_history.return_value = [
        {'date': '2026-08-18', 'close': 100.0},
        {'date': '2026-08-19', 'close': 101.5},
    ]
    asset = _seed_asset(db)

    resp = auth_client.get(f'/api/assets/{asset.id}/prices?range=1M')

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['range'] == '1M'
    assert payload['dates'] == ['2026-08-18', '2026-08-19']
    assert payload['close'] == [100.0, 101.5]
    mock_get_provider.return_value.get_price_history.assert_called_once_with('RY.TO', '1M')


def test_asset_prices_endpoint_defaults_invalid_range_to_1y(auth_client, db):
    asset = _seed_asset(db)
    with patch('src.routes.stockViews.get_provider') as mock_get_provider:
        mock_get_provider.return_value.get_price_history.return_value = []
        resp = auth_client.get(f'/api/assets/{asset.id}/prices?range=bogus')

    assert resp.get_json()['range'] == '1Y'


def test_asset_prices_endpoint_404_for_unknown_asset(auth_client, db):
    resp = auth_client.get('/api/assets/999999/prices')
    assert resp.status_code == 404
