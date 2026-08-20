from bs4 import BeautifulSoup

from src.models import UserModel
from src.routes.auth import _resolve_google_user, _safe_next


def _claims(**overrides):
    base = {
        "sub": "google-subject-1",
        "email": "nuevo@example.com",
        "email_verified": True,
        "name": "Manuel Medina",
        "given_name": "Manuel",
        "picture": "https://lh3.googleusercontent.com/a/photo",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------- registro


def test_register_creates_the_user_and_signs_them_in(client, db):
    resp = client.post(
        "/register",
        data={
            "username": "newuser",
            "email": "NewUser@Example.com",
            "password": "s3cret-pw",
        },
    )

    # Straight to the dashboard, not back to the login form.
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"

    user = UserModel.query.filter_by(username="newuser").first()
    assert user is not None
    assert user.email == "newuser@example.com"

    # The session is live: a protected page answers without a second login.
    assert client.get("/portfolio").status_code == 200


def test_register_honours_a_safe_next(client, db):
    resp = client.post(
        "/register?next=/dividends",
        data={"username": "nextuser", "email": "next@example.com", "password": "s3cret-pw"},
    )
    assert resp.headers["Location"] == "/dividends"


def test_register_ignores_an_offsite_next(client, db):
    resp = client.post(
        "/register?next=https://evil.example/phish",
        data={"username": "safeuser", "email": "safe@example.com", "password": "s3cret-pw"},
    )
    assert resp.headers["Location"] == "/dashboard"


def test_register_rejects_a_taken_username_on_the_field(client, user):
    resp = client.post(
        "/register",
        data={"username": user.username, "email": "otro@example.com", "password": "s3cret-pw"},
    )

    assert resp.status_code == 200
    assert "Ese usuario ya está tomado." in resp.get_data(as_text=True)
    assert UserModel.query.filter_by(email="otro@example.com").first() is None


def test_register_rejects_a_taken_email_on_the_field(client, user):
    resp = client.post(
        "/register",
        data={"username": "otro", "email": user.email.upper(), "password": "s3cret-pw"},
    )

    assert resp.status_code == 200
    assert "Ya hay una cuenta con ese email" in resp.get_data(as_text=True)
    assert UserModel.query.filter_by(username="otro").first() is None


def test_register_rejects_a_short_password(client, db):
    resp = client.post(
        "/register",
        data={"username": "corto", "email": "corto@example.com", "password": "1234567"},
    )

    assert resp.status_code == 200
    assert "Mínimo 8 caracteres." in resp.get_data(as_text=True)
    assert UserModel.query.filter_by(username="corto").first() is None


def test_register_redirects_an_already_signed_in_visitor(auth_client):
    resp = auth_client.get("/register")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


# ------------------------------------------------------------------ login


def test_login_accepts_the_username(client, user):
    resp = client.post("/login", data={"identifier": user.username, "password": "s3cret-pw"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


def test_login_accepts_the_email(client, user):
    resp = client.post("/login", data={"identifier": user.email, "password": "s3cret-pw"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


def test_login_is_case_insensitive_on_both_identifiers(client, user):
    for identifier in (user.username.upper(), user.email.upper()):
        resp = client.post("/login", data={"identifier": identifier, "password": "s3cret-pw"})
        assert resp.status_code == 302, identifier
        client.get("/logout")


def test_login_with_wrong_password_fails(client, user):
    resp = client.post("/login", data={"identifier": user.username, "password": "nope"})

    assert resp.status_code == 200
    assert "Usuario o contraseña incorrectos." in resp.get_data(as_text=True)


def test_login_says_nothing_extra_about_an_unknown_account(client, db):
    """An unknown identifier and a wrong password must be indistinguishable —
    otherwise the form doubles as an "is this email registered here" oracle."""
    resp = client.post("/login", data={"identifier": "fantasma", "password": "whatever"})

    assert "Usuario o contraseña incorrectos." in resp.get_data(as_text=True)


def test_login_points_a_google_only_account_at_the_google_button(client, db):
    google_user = UserModel(username="googler", email="googler@example.com",
                            google_id="google-subject-9")
    db.session.add(google_user)
    db.session.commit()

    resp = client.post("/login", data={"identifier": "googler", "password": "anything"})

    body = resp.get_data(as_text=True)
    assert "Esa cuenta se creó con Google" in body


def test_login_honours_a_safe_next(client, user):
    resp = client.post("/login?next=/inbox",
                       data={"identifier": user.username, "password": "s3cret-pw"})
    assert resp.headers["Location"] == "/inbox"


def test_login_redirects_an_already_signed_in_visitor(auth_client):
    resp = auth_client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


def test_logout_requires_login(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_returns_to_the_landing_page(auth_client):
    resp = auth_client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


# ------------------------------------------------------- protección next=


def test_safe_next_accepts_only_local_paths():
    assert _safe_next("/portfolio") == "/portfolio"
    assert _safe_next("/orders?page=2") == "/orders?page=2"

    assert _safe_next(None) is None
    assert _safe_next("") is None
    assert _safe_next("https://evil.example/phish") is None
    assert _safe_next("//evil.example/phish") is None
    assert _safe_next("/\\evil.example") is None
    assert _safe_next("javascript:alert(1)") is None


# ----------------------------------------------------------------- Google


def test_google_button_is_hidden_when_the_server_has_no_credentials(client):
    body = client.get("/login").get_data(as_text=True)
    assert "Continuar con Google" not in body


def test_google_button_appears_once_credentials_are_configured(app, client):
    app.config["GOOGLE_CLIENT_ID"] = "client-id.apps.googleusercontent.com"
    app.config["GOOGLE_CLIENT_SECRET"] = "client-secret"

    for path in ("/", "/login", "/register"):
        assert "Continuar con Google" in client.get(path).get_data(as_text=True), path


def test_google_route_says_so_when_it_is_not_configured(client):
    resp = client.get("/auth/google", follow_redirects=True)

    assert resp.status_code == 200
    assert "El acceso con Google no está configurado" in resp.get_data(as_text=True)


def test_google_claims_create_a_new_account(app, db):
    user, created = _resolve_google_user(_claims())

    assert created is True
    assert user.username == "Manuel"
    assert user.email == "nuevo@example.com"
    assert user.google_id == "google-subject-1"
    assert user.full_name == "Manuel Medina"
    assert user.has_password is False


def test_google_derives_a_free_username_when_the_first_choice_is_taken(app, db):
    db.session.add(UserModel(username="Manuel", email="otro@example.com", password="s3cret-pw"))
    db.session.commit()

    user, created = _resolve_google_user(_claims())

    assert created is True
    assert user.username == "Manuel2"


def test_google_returning_visitor_matches_on_the_subject_not_the_email(app, db):
    existing = UserModel(username="manu", email="viejo@example.com",
                         google_id="google-subject-1")
    db.session.add(existing)
    db.session.commit()

    user, created = _resolve_google_user(_claims(email="nuevo@example.com"))

    assert created is False
    assert user.id == existing.id
    # The local email stays put; the subject is the identity, not the address.
    assert user.email == "viejo@example.com"
    assert user.full_name == "Manuel Medina"


def test_google_links_onto_an_existing_password_account(app, db, user):
    linked, created = _resolve_google_user(_claims(email=user.email))

    assert created is False
    assert linked.id == user.id
    assert linked.google_id == "google-subject-1"
    # Linking must not cost them their password login.
    assert linked.check_password("s3cret-pw")


def test_google_refuses_to_link_an_unverified_email(app, db, user):
    resolved, created = _resolve_google_user(_claims(email=user.email, email_verified=False))

    assert resolved is None
    assert created is False
    assert UserModel.query.filter_by(email=user.email).first().google_id is None


def test_google_refuses_claims_without_an_email(app, db):
    assert _resolve_google_user(_claims(email=None)) == (None, False)
    assert _resolve_google_user({}) == (None, False)


# ------------------------------------------------------------ navegación


def test_landing_is_public_and_leads_with_one_call_to_action(client):
    resp = client.get("/")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Crear cuenta gratis" in body
    assert 'href="/register"' in body
    assert 'href="/login"' in body


def test_home_sends_a_signed_in_user_to_the_dashboard(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


def test_auth_screens_drop_the_app_nav(client):
    """The nav's own "Iniciar sesión / Crear cuenta" buttons are noise on the
    very pages they point at, so the auth screens replace the chrome."""
    soup = BeautifulSoup(client.get("/login").data, "html.parser")
    assert soup.find("nav") is None


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
