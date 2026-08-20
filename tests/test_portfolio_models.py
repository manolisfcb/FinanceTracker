from datetime import date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from src.models import (
    Account,
    AccountType,
    AllocationTarget,
    Asset,
    DividendReceived,
    OrderModel,
    OrderType,
    PortfolioSnapshotModel,
)


def _asset(db, symbol='RY'):
    asset = Asset(symbol=symbol, yahoo_symbol=f'{symbol}.TO', exchange='TSX', currency='CAD', name='Royal Bank')
    db.session.add(asset)
    db.session.commit()
    return asset


def _account(db, user, name='Questrade Margin', type_=AccountType.MARGIN):
    account = Account(user_id=user.id, type=type_, name=name)
    db.session.add(account)
    db.session.commit()
    return account


def test_account_unique_user_name(db, user):
    db.session.add(Account(user_id=user.id, type=AccountType.MARGIN, name='Margin'))
    db.session.commit()

    db.session.add(Account(user_id=user.id, type=AccountType.TFSA, name='Margin'))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_account_is_registered(db, user):
    tfsa = Account(user_id=user.id, type=AccountType.TFSA, name='TFSA')
    margin = Account(user_id=user.id, type=AccountType.MARGIN, name='Margin')
    assert tfsa.is_registered is True
    assert margin.is_registered is False


def test_order_requires_account_id(db, user):
    asset = _asset(db)
    order = OrderModel(
        user_id=user.id,
        asset_id=asset.id,
        type=OrderType.BUY,
        quantity=10,
        price=100.0,
        currency='CAD',
        executed_at=datetime(2026, 1, 1),
    )
    db.session.add(order)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_order_import_hash_unique(db, user):
    asset = _asset(db)
    account = _account(db, user)

    db.session.add(
        OrderModel(
            user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
            quantity=10, price=100.0, currency='CAD', executed_at=datetime(2026, 1, 1),
            import_hash='abc123',
        )
    )
    db.session.commit()

    db.session.add(
        OrderModel(
            user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.SELL,
            quantity=5, price=110.0, currency='CAD', executed_at=datetime(2026, 1, 2),
            import_hash='abc123',
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_dividend_received_unique_user_asset_paydate(db, user):
    asset = _asset(db)
    db.session.add(
        DividendReceived(
            user_id=user.id, asset_id=asset.id, pay_date=date(2026, 3, 1),
            quantity_held=10, total_amount=5.0, currency='CAD',
        )
    )
    db.session.commit()

    db.session.add(
        DividendReceived(
            user_id=user.id, asset_id=asset.id, pay_date=date(2026, 3, 1),
            quantity_held=10, total_amount=5.0, currency='CAD',
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_portfolio_snapshot_unique_user_date_account(db, user):
    account = _account(db, user)
    db.session.add(
        PortfolioSnapshotModel(
            user_id=user.id, account_id=account.id, date=date(2026, 8, 20),
            patrimony_cad=100.0, total_invested_cad=90.0, dividends_accum_cad=0.0,
        )
    )
    db.session.commit()

    db.session.add(
        PortfolioSnapshotModel(
            user_id=user.id, account_id=account.id, date=date(2026, 8, 20),
            patrimony_cad=200.0, total_invested_cad=190.0, dividends_accum_cad=0.0,
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_allocation_target_unique_user_asset(db, user):
    asset = _asset(db)
    db.session.add(AllocationTarget(user_id=user.id, asset_id=asset.id, target_percent=10.0))
    db.session.commit()

    db.session.add(AllocationTarget(user_id=user.id, asset_id=asset.id, target_percent=20.0))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
