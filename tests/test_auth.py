from src.models import UserModel


def test_register_creates_user(client, db):
    resp = client.post(
        "/register",
        data={
            "name": "newuser",
            "email": "newuser@example.com",
            "password": "s3cret-pw",
            "confirm_password": "s3cret-pw",
        },
    )
    assert resp.status_code == 200
    assert UserModel.query.filter_by(email="newuser@example.com").first() is not None


def test_login_with_correct_password_succeeds(client, user):
    resp = client.post(
        "/login",
        data={"username": user.username, "password": "s3cret-pw"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Logged in successfully" in resp.data


def test_login_with_wrong_password_fails(client, user):
    resp = client.post(
        "/login",
        data={"username": user.username, "password": "wrong-password"},
    )
    assert resp.status_code == 200
    assert b"Invalid login" in resp.data


def test_logout_requires_login(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
