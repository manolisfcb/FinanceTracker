from datetime import date

from src.models import Asset, Fundamentals


def _seed_two_assets(db):
    ry = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD',
               name='Royal Bank', sector='Financial Services', website='https://www.rbc.com',
               logo_url='https://logo.clearbit.com/rbc.com')
    aapl = Asset(symbol='AAPL', yahoo_symbol='AAPL', exchange='US', currency='USD',
                 name='Apple Inc.', sector='Technology', website='https://www.apple.com',
                 logo_url='https://logo.clearbit.com/apple.com')
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
    assert 'screener-shell' not in body
    assert 'HX-Request' in resp.vary


def test_screener_htmx_owner_survives_layout_swaps(auth_client, db):
    _seed_two_assets(db)
    full_body = auth_client.get('/stocks').get_data(as_text=True)

    assert 'id="screener-shell"' in full_body
    assert 'hx-target="#screener-container"' in full_body
    assert 'hx-swap="outerHTML show:none"' in full_body
    assert 'hx-sync="#screener-shell:replace"' in full_body

    # The swapped fragment must not own hx-boost itself. It remains a child of
    # the stable shell, so the next click (Cards -> Lista) is boosted as well.
    cards_fragment = auth_client.get(
        '/stocks?view=cards', headers={'HX-Request': 'true'},
    ).get_data(as_text=True)
    assert 'id="screener-container"' in cards_fragment
    assert 'hx-boost="true"' not in cards_fragment
    assert 'href="/stocks?view=list"' in cards_fragment

    list_fragment = auth_client.get(
        '/stocks?view=list', headers={'HX-Request': 'true'},
    ).get_data(as_text=True)
    assert '<table' in list_fragment


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


def test_screener_defaults_to_the_list_view(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks').get_data(as_text=True)
    assert '<table' in body
    assert 'tn-seg-on' in body


def test_screener_cards_view_renders_cards_not_a_table(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?view=cards').get_data(as_text=True)
    assert '<table' not in body
    assert 'Royal Bank' in body
    assert 'Market cap' in body


def test_screener_unknown_view_falls_back_to_the_list(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?view=nonsense').get_data(as_text=True)
    assert '<table' in body


def test_toolbar_exchange_chip_links_drop_that_exchange(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks').get_data(as_text=True)
    # Nothing filtered yet, so every chip is lit and each one links to the
    # set without itself.
    assert 'exchange=US' in body
    assert 'exchange=TSX' in body


def test_toolbar_labels_the_active_preset(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?pe_max=20').get_data(as_text=True)
    assert 'P/E: <span class="sel-value">&lt; 20</span>' in body


def test_toolbar_describes_bounds_that_match_no_preset(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?pe_max=17.5').get_data(as_text=True)
    assert '&lt; 17.5' in body


def test_add_filter_opens_an_extra_dropdown_without_filtering_yet(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?add=payout_ratio').get_data(as_text=True)
    assert 'Payout: <span class="sel-value">cualquiera</span>' in body
    # Still unfiltered: both companies are there.
    assert 'Royal Bank' in body
    assert 'Apple Inc.' in body


def test_an_extra_filter_with_a_value_shows_even_without_add(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?market_cap_min=1000000000').get_data(as_text=True)
    assert 'Mkt cap: <span class="sel-value">&gt; 1B</span>' in body


def test_dividend_yield_presets_filter_on_fractions_not_percents(auth_client, db):
    _seed_two_assets(db)
    # RY yields 4%, AAPL 0.5% — the "> 3%" preset is dividend_yield_min=0.03.
    body = auth_client.get('/stocks?dividend_yield_min=0.03').get_data(as_text=True)
    assert 'Royal Bank' in body
    assert 'Apple Inc.' not in body


def test_sector_filter_labels_the_chosen_sector(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?sector=Technology').get_data(as_text=True)
    assert 'Sector: <span class="sel-value">Technology</span>' in body
    assert 'Apple Inc.' in body
    assert 'Royal Bank' not in body


def test_csv_export_keeps_exchange_and_name_columns(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks/export.csv').get_data(as_text=True)
    header = body.splitlines()[0]
    assert header.startswith('symbol,name,exchange,sector')
    assert 'Royal Bank,TSX' in body


def test_view_and_filters_survive_a_sort_link(auth_client, db):
    _seed_two_assets(db)
    body = auth_client.get('/stocks?view=cards&exchange=TSX').get_data(as_text=True)
    assert 'view=cards' in body
    assert 'exchange=TSX' in body


def test_rows_and_cards_carry_the_company_url_for_whole_row_clicks(auth_client, db):
    _seed_two_assets(db)
    list_body = auth_client.get('/stocks').get_data(as_text=True)
    cards_body = auth_client.get('/stocks?view=cards').get_data(as_text=True)
    assert 'data-row-href="/stocks/TSX/RY"' in list_body
    assert 'data-row-href="/stocks/TSX/RY"' in cards_body


def test_list_and_cards_render_company_icons_from_the_existing_website(auth_client, db):
    _seed_two_assets(db)
    list_body = auth_client.get('/stocks').get_data(as_text=True)
    cards_body = auth_client.get('/stocks?view=cards').get_data(as_text=True)

    expected = 'https://www.google.com/s2/favicons?domain=rbc.com&amp;sz=128'
    assert expected in list_body
    assert expected in cards_body
    assert 'logo.clearbit.com' not in list_body
    assert 'logo.clearbit.com' not in cards_body
