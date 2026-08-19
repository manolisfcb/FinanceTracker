import pytest

from src import create_app
from src.extensions import db as _db


@pytest.fixture()
def app():
    application = create_app("testing")

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def user(app, db):
    from src.models import UserModel

    u = UserModel(username="tester", email="tester@example.com", password="s3cret-pw")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def auth_client(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return client
