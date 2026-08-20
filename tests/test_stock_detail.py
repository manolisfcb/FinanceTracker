from datetime import date, datetime
from unittest.mock import patch

from src.models import Asset, CompanyEvent, CompanyEventKind, DividendHistory, Fundamentals


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


def test_stock_detail_lists_news(auth_client, db):
    asset = _seed_asset(db)
    db.session.add(CompanyEvent(
        asset_id=asset.id, kind=CompanyEventKind.NEWS, source='GOOGLE', external_id='n-1',
        title='RBC nombra nuevo CEO', summary='Publicado por TradingView.',
        url='https://news.example/ry', published_at=datetime(2026, 8, 18, 9, 0),
    ))
    db.session.commit()

    body = auth_client.get('/stocks/TSX/RY').get_data(as_text=True)

    assert 'RBC nombra nuevo CEO' in body
    assert 'https://news.example/ry' in body
    assert 'Sin noticias registradas todavía' not in body


def test_stock_detail_shows_empty_state_without_news(auth_client, db):
    _seed_asset(db)
    assert 'Sin noticias registradas todavía' in auth_client.get('/stocks/TSX/RY').get_data(as_text=True)


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


@patch('src.services.fundamentals.get_provider')
@patch('src.routes.stockViews.get_provider')
def test_stock_detail_renders_indicators_with_their_explanations(
    mock_view_provider, mock_fundamentals_provider, auth_client, db
):
    mock_view_provider.return_value.get_quote.return_value = None
    mock_fundamentals_provider.return_value.get_statement_metrics.return_value = None
    mock_fundamentals_provider.return_value.get_fundamentals.return_value = None
    asset = _seed_asset(db)
    db.session.add(Fundamentals(
        asset_id=asset.id, as_of_date=date(2026, 8, 19),
        market_cap=2400.0, ebit=200.0, total_assets=2000.0, total_liabilities=1200.0,
        total_equity=800.0, net_debt=600.0, ebitda=300.0, revenue=1000.0,
        total_debt=700.0, tax_rate=0.25, book_value_per_share=12.5,
    ))
    db.session.commit()

    body = auth_client.get('/stocks/TSX/RY').get_data(as_text=True)

    # Suno-style indicators the page didn't have before.
    assert 'P/EBIT' in body
    assert 'Deuda neta/EBITDA' in body
    assert 'Giro del activo' in body
    assert 'ROIC' in body
    assert 'VPA' in body
    # ...each with its own "?" explanation.
    assert 'class="tn-help"' in body
    assert 'Cuántos años de EBITDA harían falta' in body
    # Derived on the way in, not left blank: 2400 / 200 and 600 / 300.
    assert '12.00' in body
    assert '2.00' in body


@patch('src.services.fundamentals.get_provider')
@patch('src.routes.stockViews.get_provider')
def test_cagr_label_states_the_span_it_measured(
    mock_view_provider, mock_fundamentals_provider, auth_client, db
):
    mock_view_provider.return_value.get_quote.return_value = None
    mock_fundamentals_provider.return_value.get_statement_metrics.return_value = None
    mock_fundamentals_provider.return_value.get_fundamentals.return_value = None
    asset = _seed_asset(db)
    db.session.add(Fundamentals(
        asset_id=asset.id, as_of_date=date(2026, 8, 19),
        total_assets=2000.0, revenue_cagr=0.1, revenue_cagr_years=3,
    ))
    db.session.commit()

    body = auth_client.get('/stocks/TSX/RY').get_data(as_text=True)

    assert 'CAGR ingresos (3A)' in body
    assert 'CAGR ingresos (5A)' not in body
