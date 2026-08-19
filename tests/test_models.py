from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from src.models import Asset, Fundamentals


def test_asset_unique_symbol_exchange(db):
    db.session.add(Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank'))
    db.session.commit()

    db.session.add(Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank dup'))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_asset_same_symbol_different_exchange_is_allowed(db):
    db.session.add(Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank'))
    db.session.add(Asset(symbol='RY', yahoo_symbol='RY', exchange='US', currency='USD', name='Royal Bank ADR'))
    db.session.commit()

    assert Asset.query.count() == 2


def test_asset_serialize(db):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank', is_active=True)
    db.session.add(asset)
    db.session.commit()

    data = asset.serialize()
    assert data['symbol'] == 'RY'
    assert data['exchange'] == 'TSX'
    assert data['is_active'] is True


def test_fundamentals_unique_asset_and_date(db):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank')
    db.session.add(asset)
    db.session.commit()

    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 19), pe=12.3))
    db.session.commit()

    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 19), pe=99.9))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_fundamentals_same_asset_different_date_is_allowed(db):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank')
    db.session.add(asset)
    db.session.commit()

    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 18), pe=12.3))
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date(2026, 8, 19), pe=12.5))
    db.session.commit()

    assert Fundamentals.query.filter_by(asset_id=asset.id).count() == 2
