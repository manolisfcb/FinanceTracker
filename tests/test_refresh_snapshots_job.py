from datetime import date, datetime

from src.models import Account, AccountType, Asset, Fundamentals, OrderModel, OrderType, PortfolioSnapshotModel
from src.resources.jobs.daily_portfolio_snapshots import _snapshot_all_users


def test_snapshot_writes_total_and_per_account_rows(app, db, user):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank')
    db.session.add(asset)
    db.session.commit()

    account = Account(user_id=user.id, type=AccountType.MARGIN, name='Margin')
    db.session.add(account)
    db.session.commit()

    db.session.add(
        OrderModel(
            user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
            quantity=10, price=100.0, currency='CAD', executed_at=datetime(2026, 1, 1),
        )
    )
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date.today(), price=110.0))
    db.session.commit()

    with app.app_context():
        items = _snapshot_all_users()
        db.session.commit()

    assert items == 1
    snapshots = PortfolioSnapshotModel.query.filter_by(user_id=user.id).all()
    assert len(snapshots) == 2

    total_row = next(s for s in snapshots if s.account_id is None)
    account_row = next(s for s in snapshots if s.account_id == account.id)
    assert total_row.patrimony_cad == 1100.0
    assert account_row.patrimony_cad == 1100.0
    assert total_row.unrealized_pnl_cad == 100.0
    assert total_row.realized_pnl_cad == 0.0
    assert total_row.total_return_percent == 10.0
    assert total_row.allocation == {str(asset.id): 100.0}


def test_snapshot_rerun_same_day_updates_instead_of_duplicating(app, db, user):
    asset = Asset(symbol='RY', yahoo_symbol='RY.TO', exchange='TSX', currency='CAD', name='Royal Bank')
    db.session.add(asset)
    db.session.commit()
    account = Account(user_id=user.id, type=AccountType.MARGIN, name='Margin')
    db.session.add(account)
    db.session.commit()
    db.session.add(
        OrderModel(
            user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
            quantity=10, price=100.0, currency='CAD', executed_at=datetime(2026, 1, 1),
        )
    )
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date.today(), price=100.0))
    db.session.commit()

    with app.app_context():
        _snapshot_all_users()
        db.session.commit()
        _snapshot_all_users()
        db.session.commit()

    assert PortfolioSnapshotModel.query.filter_by(user_id=user.id).count() == 2
