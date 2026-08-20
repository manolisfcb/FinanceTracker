from datetime import date
from unittest.mock import MagicMock, patch

from src.models import Account, AccountType, Asset, Fundamentals
from src.resources.jobs.refresh_quotes import refresh_asset_quote


def test_refresh_asset_quote_writes_crypto_price(db):
    asset = Asset(
        symbol='BTC', yahoo_symbol='BTC-CAD', exchange='CRYPTO',
        currency='CAD', name='Bitcoin', sector='Cryptoassets',
    )
    db.session.add(asset)
    db.session.flush()
    provider = MagicMock()
    provider.get_quote.return_value = {'price': 98_722.20, 'currency': 'CAD'}

    assert refresh_asset_quote(asset, provider) is True
    db.session.flush()

    snapshot = Fundamentals.query.filter_by(asset_id=asset.id, as_of_date=date.today()).one()
    assert snapshot.price == 98_722.20
    provider.get_quote.assert_called_once_with('BTC-CAD')


def test_refresh_asset_quote_keeps_yahoo_quote_currency_on_the_asset(db):
    asset = Asset(
        symbol='AAPL', yahoo_symbol='AAPL', exchange='US',
        currency='CAD', name='Apple Inc.', sector='Technology',
    )
    db.session.add(asset)
    db.session.flush()
    provider = MagicMock()
    provider.get_quote.return_value = {'price': 316.27, 'currency': 'USD'}

    assert refresh_asset_quote(asset, provider) is True
    assert asset.currency == 'USD'


def test_refresh_asset_quote_does_not_create_empty_snapshot(db):
    asset = Asset(
        symbol='BTC', yahoo_symbol='BTC-CAD', exchange='CRYPTO',
        currency='CAD', name='Bitcoin', sector='Cryptoassets',
    )
    db.session.add(asset)
    db.session.flush()
    provider = MagicMock()
    provider.get_quote.return_value = {'price': None, 'currency': 'CAD'}

    assert refresh_asset_quote(asset, provider) is False
    assert Fundamentals.query.filter_by(asset_id=asset.id).count() == 0


@patch('src.routes.orders.refresh_asset_quote')
def test_new_order_requests_an_initial_quote(mock_refresh, app, auth_client, db, user):
    app.config['REFRESH_QUOTE_ON_ORDER_CREATE'] = True
    account = Account(user_id=user.id, type=AccountType.CRYPTO, name='Crypto')
    db.session.add(account)
    db.session.commit()
    mock_refresh.return_value = False

    response = auth_client.post(
        '/orders/add',
        data={
            'account': str(account.id),
            'asset_symbol': 'BTC',
            'type': 'BUY',
            'quantity': '0.001',
            'price': '90000',
            'fees': '0',
            'currency': 'CAD',
            'executed_at': '2026-08-20',
        },
    )

    assert response.status_code == 302
    quoted_asset = mock_refresh.call_args.args[0]
    assert quoted_asset.symbol == 'BTC'
    assert quoted_asset.yahoo_symbol == 'BTC-CAD'
