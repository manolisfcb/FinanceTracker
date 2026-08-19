from datetime import date

from src.models import Asset, Fundamentals


def _seed_two_assets(db):
    ry = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD',
               name='Royal Bank', sector='Financial Services')
    aapl = Asset(symbol='AAPL', yahoo_symbol='AAPL', exchange='US', currency='USD',
                 name='Apple Inc.', sector='Technology')
    db.session.add_all([ry, aapl])
    db.session.commit()

    db.session.add_all([
        Fundamentals(asset_id=ry.id, as_of_date=date(2026, 8, 19), pe=12.0,
                     market_cap=180_000_000_000, dividend_yield=0.04),
        Fundamentals(asset_id=aapl.id, as_of_date=date(2026, 8, 19), pe=30.0,
                     market_cap=3_000_000_000_000, dividend_yield=0.005),
    ])
    db.session.commit()
    return ry, aapl


def test_screener_renders_seeded_assets(auth_client, db):
    _seed_two_assets(db)
    resp = auth_client.get('/stocks')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Royal Bank' in body
    assert 'Apple Inc.' in body


def test_screener_filters_by_exchange(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?exchange=TSX').get_data(as_text=True)
    assert 'Royal Bank' in body
    assert 'Apple Inc.' not in body


def test_screener_range_filter_by_pe(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?pe_max=20').get_data(as_text=True)
    assert 'Royal Bank' in body
    assert 'Apple Inc.' not in body


def test_screener_search_by_name(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?q=apple').get_data(as_text=True)
    assert 'Apple Inc.' in body
    assert 'Royal Bank' not in body


def test_screener_htmx_request_returns_partial_not_full_page(auth_client, db):
    _seed_two_assets(db)
    resp = auth_client.get('/stocks', headers={'HX-Request': 'true'})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '<html' not in body.lower()
    assert 'screener-container' in body


def test_screener_csv_export(auth_client, db):
    _seed_two_assets(db)
    resp = auth_client.get('/stocks/export.csv')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'
    body = resp.get_data(as_text=True)
    assert 'RY' in body
    assert 'AAPL' in body


def test_screener_shows_assets_without_fundamentals_yet(auth_client, db):
    db.session.add(Asset(symbol='NEWCO', yahoo_symbol='NEWCO.TO', exchange='TSX',
                          currency='CAD', name='Freshly Seeded Inc.'))
    db.session.commit()

    resp = auth_client.get('/stocks')
    assert resp.status_code == 200
    assert 'Freshly Seeded Inc.' in resp.get_data(as_text=True)


def test_screener_invalid_range_filter_is_ignored_not_500(auth_client, db):
    _seed_two_assets(db)
    resp = auth_client.get('/stocks?pe_min=not-a-number')
    assert resp.status_code == 200
