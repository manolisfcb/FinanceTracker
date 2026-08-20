from datetime import date, datetime, timedelta

from src.models import (
    Account,
    AccountType,
    Asset,
    CompanyEvent,
    CompanyEventKind,
    CompanyEventRead,
    DividendHistory,
    DividendReceived,
    OrderModel,
    OrderType,
    UserModel,
)


def _held_asset(db, user, symbol='RY', exchange='TSX'):
    asset = Asset(
        symbol=symbol, yahoo_symbol=f'{symbol}.TO', exchange=exchange,
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
        quantity=100, price=50.0, currency='CAD', executed_at=datetime(2026, 1, 1),
    ))
    db.session.commit()
    return asset


def _event(db, asset, kind=CompanyEventKind.FILING, external_id='acc-1', published_at=None):
    event = CompanyEvent(
        asset_id=asset.id, kind=kind, source='EDGAR', external_id=external_id,
        title=f'{asset.symbol} — 8-K', summary='Nuevo filing',
        published_at=published_at or datetime.utcnow(),
        event_date=date.today(),
    )
    db.session.add(event)
    db.session.commit()
    return event


def test_dividends_page_generates_suggestions_from_history(auth_client, db, user):
    asset = _held_asset(db, user)
    db.session.add(DividendHistory(
        asset_id=asset.id, ex_date=date(2026, 3, 1), pay_date=date(2026, 3, 15),
        amount=1.42, currency='CAD',
    ))
    db.session.commit()

    resp = auth_client.get('/dividends')

    assert resp.status_code == 200
    suggestion = DividendReceived.query.filter_by(user_id=user.id).one()
    assert suggestion.confirmed is False
    assert suggestion.total_amount == 142.0


def test_dividends_page_renders_without_any_data(auth_client):
    assert auth_client.get('/dividends').status_code == 200


def test_confirm_marks_row_confirmed(auth_client, db, user):
    asset = _held_asset(db, user)
    row = DividendReceived(
        user_id=user.id, asset_id=asset.id, pay_date=date(2026, 3, 15),
        quantity_held=100, total_amount=142.0, currency='CAD', confirmed=False,
    )
    db.session.add(row)
    db.session.commit()

    resp = auth_client.post(f'/dividends/{row.id}/confirm', headers={'HX-Request': 'true'})

    assert resp.status_code == 204
    assert DividendReceived.query.get(row.id).confirmed is True


def test_dismiss_marks_row_dismissed(auth_client, db, user):
    asset = _held_asset(db, user)
    row = DividendReceived(
        user_id=user.id, asset_id=asset.id, pay_date=date(2026, 3, 15),
        quantity_held=100, total_amount=142.0, currency='CAD', confirmed=False,
    )
    db.session.add(row)
    db.session.commit()

    resp = auth_client.post(f'/dividends/{row.id}/dismiss', headers={'HX-Request': 'true'})

    assert resp.status_code == 204
    assert DividendReceived.query.get(row.id).dismissed is True


def test_cannot_confirm_another_users_dividend(auth_client, db, user):
    asset = _held_asset(db, user)
    other = UserModel(username='other', email='other@example.com', password='pw')
    db.session.add(other)
    db.session.commit()
    row = DividendReceived(
        user_id=other.id, asset_id=asset.id, pay_date=date(2026, 3, 15),
        quantity_held=10, total_amount=14.0, currency='CAD', confirmed=False,
    )
    db.session.add(row)
    db.session.commit()

    resp = auth_client.post(f'/dividends/{row.id}/confirm')

    assert resp.status_code == 404
    assert DividendReceived.query.get(row.id).confirmed is False


def test_inbox_only_shows_events_for_held_assets(auth_client, db, user):
    held = _held_asset(db, user, symbol='RY')
    other = Asset(symbol='SU', yahoo_symbol='SU.TO', exchange='TSX', currency='CAD', name='Suncor')
    db.session.add(other)
    db.session.commit()
    _event(db, held, external_id='held-1')
    _event(db, other, external_id='other-1')

    resp = auth_client.get('/inbox')

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'RY · RY Inc.' in body
    assert 'SU · Suncor' not in body


def test_inbox_filters_by_kind(auth_client, db, user):
    asset = _held_asset(db, user)
    _event(db, asset, kind=CompanyEventKind.FILING, external_id='f-1')
    _event(db, asset, kind=CompanyEventKind.EARNINGS, external_id='e-1')

    resp = auth_client.get('/inbox?kind=EARNINGS', headers={'HX-Request': 'true'})
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'Resultados' in body
    assert 'Filing<' not in body


def test_mark_read_is_idempotent(auth_client, db, user):
    asset = _held_asset(db, user)
    event = _event(db, asset)

    assert auth_client.post(f'/inbox/{event.id}/read').status_code == 204
    assert auth_client.post(f'/inbox/{event.id}/read').status_code == 204

    assert CompanyEventRead.query.filter_by(user_id=user.id, company_event_id=event.id).count() == 1


def test_cannot_mark_read_an_event_for_an_unheld_asset(auth_client, db, user):
    _held_asset(db, user, symbol='RY')
    other = Asset(symbol='SU', yahoo_symbol='SU.TO', exchange='TSX', currency='CAD', name='Suncor')
    db.session.add(other)
    db.session.commit()
    event = _event(db, other, external_id='other-1')

    assert auth_client.post(f'/inbox/{event.id}/read').status_code == 404


def test_mark_all_read_clears_the_nav_badge(auth_client, db, user):
    asset = _held_asset(db, user)
    _event(db, asset, external_id='a-1', published_at=datetime.utcnow() - timedelta(days=1))
    _event(db, asset, external_id='a-2')

    assert '<span class="num text-[10px]' in auth_client.get('/inbox').get_data(as_text=True)

    auth_client.post('/inbox/read-all', headers={'HX-Request': 'true'})

    assert CompanyEventRead.query.filter_by(user_id=user.id).count() == 2
    assert '<span class="num text-[10px]' not in auth_client.get('/inbox').get_data(as_text=True)
