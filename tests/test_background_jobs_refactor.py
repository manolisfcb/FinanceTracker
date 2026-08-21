from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.extensions import scheduler
from src.models import (
    Account,
    AccountType,
    Asset,
    AssetPrice,
    AssetType,
    Fundamentals,
    ListingStatus,
    OrderModel,
    OrderType,
)
from src.services.job_policies import (
    needs_fundamentals_refresh,
    relevant_assets,
)
from src.services.market_prices import refresh_asset_price


def _holding(db, user, asset, quantity=10):
    account = Account.query.filter_by(user_id=user.id).first()
    if account is None:
        account = Account(user_id=user.id, type=AccountType.MARGIN, name='Margin')
        db.session.add(account)
        db.session.flush()
    db.session.add(OrderModel(
        user_id=user.id,
        asset_id=asset.id,
        account_id=account.id,
        type=OrderType.BUY,
        quantity=quantity,
        price=100,
        fees=0,
        currency=asset.currency,
        fx_rate_to_cad=1,
        executed_at=datetime(2026, 1, 1),
    ))
    db.session.commit()


def _daily_payload(close=110.0):
    return {
        'date': date(2026, 8, 21),
        'open': 108.0,
        'close': close,
        'previous_close': 107.0,
        'high': 111.0,
        'low': 106.0,
        'volume': 123_456,
        'currency': 'CAD',
    }


def test_only_three_daily_scheduler_jobs_are_registered():
    import src.resources.jobs.daily_asset_data_refresh  # noqa: F401
    import src.resources.jobs.daily_market_refresh  # noqa: F401
    import src.resources.jobs.daily_portfolio_snapshots  # noqa: F401

    assert {job.id for job in scheduler.get_jobs()} == {
        'daily_market_refresh',
        'daily_asset_data_refresh',
        'daily_portfolio_snapshots',
    }


def test_relevant_assets_include_holdings_and_recent_views_but_not_sold_positions(db, user):
    held = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC')
    sold = Asset(symbol='SU', yahoo_symbol='SU.TO', exchange='TSX', currency='CAD', name='Suncor')
    viewed = Asset(
        symbol='TD', yahoo_symbol='TD.TO', exchange='TSX', currency='CAD', name='TD',
        last_viewed_at=datetime.utcnow(),
    )
    db.session.add_all([held, sold, viewed])
    db.session.flush()
    _holding(db, user, held)
    _holding(db, user, sold)
    account = Account.query.filter_by(user_id=user.id).one()
    db.session.add(OrderModel(
        user_id=user.id, asset_id=sold.id, account_id=account.id, type=OrderType.SELL,
        quantity=10, price=105, fees=0, currency='CAD', fx_rate_to_cad=1,
        executed_at=datetime(2026, 2, 1),
    ))
    db.session.commit()

    assert {asset.id for asset in relevant_assets()} == {held.id, viewed.id}


def test_fundamentals_policy_excludes_crypto_and_non_active_listings(db):
    stock = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC')
    crypto = Asset(
        symbol='BTC', yahoo_symbol='BTC-CAD', exchange='CRYPTO', currency='CAD',
        name='Bitcoin', sector='Cryptoassets',
    )
    unknown = Asset(
        symbol='OLD', yahoo_symbol='OLD', exchange='US', currency='USD', name='Old Co',
        listing_status=ListingStatus.UNKNOWN,
    )
    db.session.add_all([stock, crypto, unknown])
    db.session.flush()

    assert stock.asset_type == AssetType.STOCK
    assert needs_fundamentals_refresh(stock) is True
    assert crypto.asset_type == AssetType.CRYPTO
    assert crypto.fundamentals_enabled is False
    assert needs_fundamentals_refresh(crypto) is False
    assert needs_fundamentals_refresh(unknown) is False


def test_daily_price_upsert_is_idempotent_and_tracks_ohlcv(db):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC')
    db.session.add(asset)
    db.session.flush()
    provider = MagicMock()
    provider.get_daily_price.side_effect = [_daily_payload(110), _daily_payload(112)]

    first = refresh_asset_price(
        asset, provider, now=datetime(2026, 8, 21, 18, 0), cooldown_minutes=0,
    )
    db.session.commit()
    second = refresh_asset_price(
        asset, provider, now=datetime(2026, 8, 21, 18, 1), cooldown_minutes=0,
    )
    db.session.commit()

    assert first.refreshed and second.refreshed
    assert AssetPrice.query.filter_by(asset_id=asset.id).count() == 1
    row = AssetPrice.query.filter_by(asset_id=asset.id).one()
    assert row.close == 112
    assert row.open == 108
    assert row.high == 111
    assert row.volume == 123_456


def test_failures_move_asset_to_unknown_not_delisted_and_success_recovers(db):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC')
    db.session.add(asset)
    db.session.flush()
    provider = MagicMock()
    provider.get_daily_price.return_value = None

    for minute in range(3):
        assert refresh_asset_price(
            asset, provider, now=datetime(2026, 8, 21, 18, minute), cooldown_minutes=0,
        ).status == 'failed'
        db.session.commit()

    assert asset.listing_status == ListingStatus.UNKNOWN
    assert asset.listing_status != ListingStatus.DELISTED
    provider.get_daily_price.return_value = _daily_payload()
    assert refresh_asset_price(
        asset, provider, now=datetime(2026, 8, 21, 18, 4), cooldown_minutes=0,
    ).refreshed
    db.session.commit()
    assert asset.listing_status == ListingStatus.ACTIVE
    assert asset.market_data_failures == 0


@patch('src.routes.portfolio.get_provider')
def test_manual_refresh_uses_global_per_asset_cooldown(mock_get_provider, auth_client, db, user):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC')
    db.session.add(asset)
    db.session.flush()
    _holding(db, user, asset)
    mock_get_provider.return_value.get_daily_price.return_value = _daily_payload()

    first = auth_client.post('/portfolio/refresh-prices')
    second = auth_client.post('/portfolio/refresh-prices')

    assert first.status_code == 302
    assert second.status_code == 302
    mock_get_provider.return_value.get_daily_price.assert_called_once_with('RY.TO')
    assert AssetPrice.query.filter_by(asset_id=asset.id).count() == 1


def test_fundamentals_freshness_is_seven_days(db):
    now = datetime(2026, 8, 21, 18, 0)
    asset = Asset(
        symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC',
        last_fundamentals_refresh_at=now - timedelta(days=6),
    )
    db.session.add(asset)
    db.session.flush()

    assert needs_fundamentals_refresh(asset, now) is False
    asset.last_fundamentals_refresh_at = now - timedelta(days=8)
    assert needs_fundamentals_refresh(asset, now) is True


def test_fundamentals_refresh_carries_forward_last_non_null_value(db):
    from src.resources.jobs.daily_asset_data_refresh import _refresh_fundamentals_data

    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC')
    db.session.add(asset)
    db.session.flush()
    db.session.add(Fundamentals(
        asset_id=asset.id, as_of_date=date.today() - timedelta(days=1),
        price=100.0, pe=12.5, roe=0.18,
    ))
    db.session.commit()

    provider = MagicMock()
    # Yahoo's info payload always carries every key, including a None for
    # whatever it doesn't have today — ROE here, as if it briefly dropped out.
    provider.get_fundamentals.return_value = {'price': 101.0, 'pe': 12.8, 'roe': None}
    _refresh_fundamentals_data(asset, provider, datetime.combine(date.today(), datetime.min.time()))
    db.session.commit()

    today_snapshot = Fundamentals.query.filter_by(asset_id=asset.id, as_of_date=date.today()).one()
    assert today_snapshot.pe == 12.8
    assert today_snapshot.roe == 0.18


def test_daily_asset_data_refresh_sweeps_fundamentals_for_unheld_assets(app, db):
    from src.resources.jobs.daily_asset_data_refresh import _daily_asset_data_refresh

    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='RBC')
    db.session.add(asset)
    db.session.commit()
    provider = MagicMock()
    provider.get_fundamentals.return_value = {'price': 100.0, 'pe': 12.5}

    with (
        patch('src.resources.jobs.daily_asset_data_refresh.get_provider', return_value=provider),
        patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers', return_value=[]),
    ):
        with app.app_context():
            result = _daily_asset_data_refresh()

    assert result.items_processed == 1
    assert result.errors == 0
    snapshot = Fundamentals.query.filter_by(asset_id=asset.id).one()
    assert snapshot.pe == 12.5


def test_asset_data_sources_are_isolated_when_news_fails(app, db, user):
    from src.resources.jobs.daily_asset_data_refresh import _daily_asset_data_refresh

    now = datetime.utcnow()
    asset = Asset(
        symbol='AAPL', yahoo_symbol='AAPL', exchange='US', currency='USD', name='Apple',
        last_dividend_refresh_at=now,
        last_fundamentals_refresh_at=now,
    )
    db.session.add(asset)
    db.session.flush()
    _holding(db, user, asset)
    news_provider = MagicMock()
    news_provider.name = 'NEWS'

    with (
        patch('src.resources.jobs.daily_asset_data_refresh.get_provider', return_value=MagicMock()),
        patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers', return_value=[news_provider]),
        patch('src.resources.jobs.daily_asset_data_refresh.ingest_filings', return_value=2),
        patch('src.resources.jobs.daily_asset_data_refresh.ingest_news', side_effect=RuntimeError('feed down')),
    ):
        with app.app_context():
            result = _daily_asset_data_refresh()

    assert result.items_processed == 2
    assert result.errors == 1
    assert asset.last_filings_refresh_at is not None
    assert asset.last_news_refresh_at is None
