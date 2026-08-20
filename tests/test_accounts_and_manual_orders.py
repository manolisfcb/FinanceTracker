from datetime import date
from unittest.mock import MagicMock, patch

import requests

from src.forms.AccountForm import AccountForm
from src.models import Account, AccountType, Asset, Fundamentals, FxRate, OrderModel


def test_account_form_offers_canadian_and_crypto_account_types(app):
    with app.test_request_context():
        choices = dict(AccountForm().type.choices)

    assert {'TFSA', 'RRSP', 'FHSA', 'RESP', 'RDSP', 'RRIF', 'LIRA', 'LIF'} <= choices.keys()
    assert 'CRYPTO' in choices


def test_user_can_create_crypto_account(auth_client, db, user):
    response = auth_client.post(
        '/accounts/add',
        data={'type': 'CRYPTO', 'name': 'Wealthsimple Crypto', 'broker': 'Wealthsimple'},
    )

    assert response.status_code == 302
    account = Account.query.filter_by(user_id=user.id, name='Wealthsimple Crypto').one()
    assert account.type == AccountType.CRYPTO


def test_user_can_add_fractional_bitcoin_order(auth_client, db, user):
    account = Account(user_id=user.id, type=AccountType.CRYPTO, name='Crypto')
    db.session.add(account)
    db.session.commit()

    response = auth_client.post(
        '/orders/add',
        data={
            'account': str(account.id),
            'asset_symbol': 'BTC',
            'type': 'BUY',
            'quantity': '0.00004355',
            'price': '90041.8374185304',
            'fees': '0',
            'currency': 'CAD',
            'executed_at': '2026-08-20',
        },
    )

    assert response.status_code == 302
    asset = Asset.query.filter_by(symbol='BTC', exchange='CRYPTO').one()
    order = OrderModel.query.filter_by(user_id=user.id, account_id=account.id, asset_id=asset.id).one()
    assert order.quantity == 0.00004355
    assert order.currency == 'CAD'

    orders_body = auth_client.get('/orders').get_data(as_text=True)
    assert '>0.00004355</td>' in orders_body


def test_user_can_add_four_decimal_fractional_share_order(auth_client, db, user):
    account = Account(user_id=user.id, type=AccountType.TFSA, name='TFSA')
    asset = Asset(
        symbol='AAPL', yahoo_symbol='AAPL', exchange='US', currency='USD', name='Apple Inc.',
    )
    db.session.add_all([account, asset])
    db.session.commit()

    response = auth_client.post(
        '/orders/add',
        data={
            'account': str(account.id),
            'asset_symbol': 'AAPL',
            'asset_id': str(asset.id),
            'type': 'BUY',
            'quantity': '0.2254',
            'price': '440.15',
            'fees': '0',
            'currency': 'CAD',
            'executed_at': '2026-08-20',
        },
    )

    assert response.status_code == 302
    order = OrderModel.query.filter_by(user_id=user.id, asset_id=asset.id).one()
    assert order.quantity == 0.2254

    orders_body = auth_client.get('/orders').get_data(as_text=True)
    assert '>0.2254</td>' in orders_body


def test_manual_order_currency_is_a_cad_usd_selector(auth_client, db, user):
    account = Account(user_id=user.id, type=AccountType.TFSA, name='TFSA')
    db.session.add(account)
    db.session.commit()

    body = auth_client.get('/orders/add').get_data(as_text=True)

    assert '<select class="tn-input" id="currency" name="currency"' in body
    assert '<option selected value="CAD">CAD — Dólar canadiense</option>' in body
    assert '<option value="USD">USD — Dólar estadounidense</option>' in body
    assert 'step="0.00000001"' in body
    assert 'placeholder="0.2254"' in body


@patch('src.services.fx.requests.get')
def test_usd_manual_order_fetches_fx_and_is_converted_in_portfolio(
    mock_get, auth_client, db, user,
):
    mock_get.return_value = MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={
            'observations': [
                {'d': '2026-08-20', 'FXUSDCAD': {'v': '1.40'}},
            ],
        }),
    )
    account = Account(user_id=user.id, type=AccountType.TFSA, name='TFSA')
    asset = Asset(
        symbol='AAPL', yahoo_symbol='AAPL', exchange='US', currency='USD', name='Apple Inc.',
    )
    db.session.add_all([account, asset])
    db.session.commit()
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 20), price=110.0))
    db.session.commit()

    response = auth_client.post(
        '/orders/add',
        data={
            'account': str(account.id),
            'asset_symbol': 'AAPL',
            'asset_id': str(asset.id),
            'type': 'BUY',
            'quantity': '10',
            'price': '100',
            'fees': '0',
            'currency': 'USD',
            'executed_at': '2026-08-20',
        },
    )

    assert response.status_code == 302
    order = OrderModel.query.filter_by(user_id=user.id, asset_id=asset.id).one()
    assert order.currency == 'USD'
    assert order.fx_rate_to_cad == 1.40
    assert FxRate.query.filter_by(date=date(2026, 8, 20), pair='USDCAD').one().rate == 1.40

    body = auth_client.get('/portfolio').get_data(as_text=True)
    assert '1,540.00' in body  # 10 × US$110 × 1.40 = C$1,540
    assert '140.00' in body  # Average acquisition price: US$100 × 1.40 = C$140


@patch('src.services.fx.requests.get')
def test_usd_manual_order_is_not_saved_without_an_fx_rate(mock_get, auth_client, db, user):
    mock_get.side_effect = requests.ConnectionError('offline')
    account = Account(user_id=user.id, type=AccountType.TFSA, name='TFSA')
    asset = Asset(
        symbol='AAPL', yahoo_symbol='AAPL', exchange='US', currency='USD', name='Apple Inc.',
    )
    db.session.add_all([account, asset])
    db.session.commit()

    response = auth_client.post(
        '/orders/add',
        data={
            'account': str(account.id),
            'asset_symbol': 'AAPL',
            'asset_id': str(asset.id),
            'type': 'BUY',
            'quantity': '10',
            'price': '100',
            'fees': '0',
            'currency': 'USD',
            'executed_at': '2026-08-20',
        },
    )

    assert response.status_code == 200
    assert OrderModel.query.filter_by(user_id=user.id).count() == 0
    assert 'La orden no se guardó' in response.get_data(as_text=True)


def test_asset_autocomplete_searches_symbol_and_company_name(auth_client, db):
    db.session.add_all([
        Asset(symbol='AAPL', yahoo_symbol='AAPL', exchange='US', currency='USD', name='Apple Inc.'),
        Asset(symbol='AP.UN', yahoo_symbol='AP-UN.TO', exchange='TSX', currency='CAD', name='Allied Properties'),
        Asset(symbol='OLD', yahoo_symbol='OLD', exchange='US', currency='USD', name='Apple Legacy', is_active=False),
    ])
    db.session.commit()

    symbol_response = auth_client.get('/orders/assets/search?q=AP')
    assert symbol_response.status_code == 200
    assert [asset['symbol'] for asset in symbol_response.get_json()['assets']] == ['AP.UN', 'AAPL']

    name_response = auth_client.get('/orders/assets/search?q=apple')
    assert [asset['symbol'] for asset in name_response.get_json()['assets']] == ['AAPL']


def test_selected_autocomplete_asset_disambiguates_duplicate_symbol(auth_client, db, user):
    account = Account(user_id=user.id, type=AccountType.TFSA, name='TFSA')
    us_asset = Asset(symbol='ABC', yahoo_symbol='ABC', exchange='US', currency='USD', name='ABC US')
    tsx_asset = Asset(symbol='ABC', yahoo_symbol='ABC.TO', exchange='TSX', currency='CAD', name='ABC Canada')
    db.session.add_all([account, us_asset, tsx_asset])
    db.session.commit()

    response = auth_client.post(
        '/orders/add',
        data={
            'account': str(account.id),
            'asset_symbol': 'ABC',
            'asset_id': str(tsx_asset.id),
            'type': 'BUY',
            'quantity': '1',
            'price': '10',
            'fees': '0',
            'currency': 'CAD',
            'executed_at': '2026-08-20',
        },
    )

    assert response.status_code == 302
    order = OrderModel.query.filter_by(user_id=user.id, account_id=account.id).one()
    assert order.asset_id == tsx_asset.id
