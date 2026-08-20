from bs4 import BeautifulSoup

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


def test_expense_control_links_live_in_profile_menu(auth_client):
    resp = auth_client.get("/dashboard")
    soup = BeautifulSoup(resp.data, "html.parser")

    primary_navigation = soup.select_one("div.hidden.md\\:flex")
    assert primary_navigation is not None
    assert "Transacciones" not in primary_navigation.get_text()
    assert "Gráficos" not in primary_navigation.get_text()
    assert "Inbox" not in primary_navigation.get_text()

    profile_button = soup.find("button", attrs={"aria-label": "Abrir menú de perfil"})
    assert profile_button is not None
    profile_menu = profile_button.find_next("div", class_="card")
    assert "Control de gastos" in profile_menu.get_text()
    assert profile_menu.find("a", href="/transactions") is not None
    assert profile_menu.find("a", href="/transactions_charts") is not None
    assert profile_menu.find("a", href="/inbox") is not None
    assert profile_menu.find("a", href="/tools/rankings") is not None
    assert profile_menu.find("a", href="/tools/comparator") is not None
    assert profile_menu.find("a", href="/logout") is not None
