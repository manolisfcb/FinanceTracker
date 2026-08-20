from src.forms.AccountForm import AccountForm
from src.models import Account, AccountType, Asset, OrderModel


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
