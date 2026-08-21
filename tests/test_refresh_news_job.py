from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.models import (
    Account,
    AccountType,
    Asset,
    CompanyEvent,
    CompanyEventKind,
    OrderModel,
    OrderType,
)
from src.resources.jobs.daily_asset_data_refresh import _refresh_all_news


def _held_asset(db, user, symbol='RY'):
    asset = Asset(
        symbol=symbol, yahoo_symbol=f'{symbol}.TO', exchange='TSX',
        currency='CAD', name=f'{symbol} Inc.',
    )
    db.session.add(asset)
    db.session.commit()

    account = Account.query.filter_by(user_id=user.id).first()
    if account is None:
        account = Account(user_id=user.id, type=AccountType.MARGIN, name='Margin')
        db.session.add(account)
        db.session.commit()

    db.session.add(OrderModel(
        user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
        quantity=10, price=100.0, currency='CAD', executed_at=datetime(2026, 1, 1),
    ))
    db.session.commit()
    return asset


def _provider(name, stories):
    provider = MagicMock()
    provider.name = name
    provider.get_news.return_value = stories
    return provider


def _story(title='RY beats expectations', url='https://news.example/1', source='MarketBeat'):
    return {
        'title': title,
        'summary': None,
        'url': url,
        'published_at': datetime(2026, 8, 17, 17, 10),
        'source_name': source,
    }


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_news_are_stored_per_asset_with_source_and_url(mock_providers, app, db, user):
    asset = _held_asset(db, user)
    mock_providers.return_value = [_provider('YAHOO', [_story()])]

    with app.app_context():
        items = _refresh_all_news()
        db.session.commit()

    assert items == 1
    event = CompanyEvent.query.filter_by(kind=CompanyEventKind.NEWS).one()
    assert event.asset_id == asset.id
    assert event.source == 'YAHOO'
    assert event.title == 'RY beats expectations'
    assert event.summary == 'Publicado por MarketBeat.'
    assert event.url == 'https://news.example/1'


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_rerun_does_not_duplicate_the_same_url(mock_providers, app, db, user):
    _held_asset(db, user)
    mock_providers.return_value = [_provider('YAHOO', [_story()])]

    with app.app_context():
        _refresh_all_news()
        db.session.commit()
        second_run = _refresh_all_news()
        db.session.commit()

    assert second_run == 0
    assert CompanyEvent.query.filter_by(kind=CompanyEventKind.NEWS).count() == 1


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_same_headline_from_two_sources_is_stored_once(mock_providers, app, db, user):
    _held_asset(db, user)
    mock_providers.return_value = [
        _provider('YAHOO', [_story(url='https://yahoo.example/a')]),
        _provider('GOOGLE', [_story(title='RY Beats Expectations!', url='https://google.example/b')]),
    ]

    with app.app_context():
        items = _refresh_all_news()
        db.session.commit()

    assert items == 1
    assert CompanyEvent.query.filter_by(kind=CompanyEventKind.NEWS).count() == 1


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_an_old_duplicate_headline_is_allowed_again(mock_providers, app, db, user):
    asset = _held_asset(db, user)
    db.session.add(CompanyEvent(
        asset_id=asset.id, kind=CompanyEventKind.NEWS, source='GOOGLE', external_id='old',
        title='RY beats expectations', published_at=datetime.utcnow() - timedelta(days=60),
    ))
    db.session.commit()
    mock_providers.return_value = [_provider('YAHOO', [_story()])]

    with app.app_context():
        items = _refresh_all_news()
        db.session.commit()

    assert items == 1


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_unheld_assets_are_skipped(mock_providers, app, db, user):
    _held_asset(db, user, symbol='RY')
    db.session.add(Asset(
        symbol='SU', yahoo_symbol='SU.TO', exchange='TSX', currency='CAD', name='Suncor',
    ))
    db.session.commit()
    provider = _provider('YAHOO', [_story()])
    mock_providers.return_value = [provider]

    with app.app_context():
        _refresh_all_news()
        db.session.commit()

    assert provider.get_news.call_count == 1


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_stories_about_other_companies_are_dropped(mock_providers, app, db, user):
    # Yahoo's feed for RY really does return Rayonier and Citizens & Northern.
    _held_asset(db, user, symbol='RY')
    mock_providers.return_value = [_provider('YAHOO', [
        _story(title='Rayonier (RYN) Q2 2026 Earnings Call Transcript', url='https://n/1'),
        _story(title='Citizens & Northern (CZNC) Beats Q2 Estimates', url='https://n/2'),
        _story(title='Why RY is Poised to Beat Earnings Estimates Again', url='https://n/3'),
    ])]

    with app.app_context():
        items = _refresh_all_news()
        db.session.commit()

    assert items == 1
    assert CompanyEvent.query.filter_by(kind=CompanyEventKind.NEWS).one().title.startswith('Why RY')


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_company_name_in_the_summary_counts_as_relevant(mock_providers, app, db, user):
    asset = _held_asset(db, user, symbol='RY')
    asset.name = 'Royal Bank of Canada'
    db.session.commit()
    story = _story(title='Bond traders agonize over shadow credit', url='https://n/4')
    story['summary'] = 'Royal Bank of Canada is among the lenders exposed.'
    mock_providers.return_value = [_provider('YAHOO', [story])]

    with app.app_context():
        assert _refresh_all_news() == 1


@patch('src.resources.jobs.daily_asset_data_refresh.get_news_providers')
def test_no_providers_configured_is_a_noop(mock_providers, app, db, user):
    _held_asset(db, user)
    mock_providers.return_value = []

    with app.app_context():
        assert _refresh_all_news() == 0

    assert CompanyEvent.query.count() == 0
