"""Container/deploy concerns: probes, scheduler ownership, proxy trust."""

import pytest
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from src import create_app
from src.extensions import db


# ------------------------------------------------------------------ probes


def test_healthz_is_public_and_cheap(client):
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_readyz_reports_the_database(client):
    resp = client.get("/readyz")

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "database": "ok"}


def test_healthz_stays_up_when_the_database_is_down(client, monkeypatch):
    """Liveness must not depend on the database.

    Two reasons this matters: restarting the container would not fix a
    database outage, and the healthcheck polls every 30s — a probe that
    queried Neon would keep its compute from ever suspending.
    """
    def _boom(*args, **kwargs):
        raise RuntimeError("database is gone")

    monkeypatch.setattr(db.session, "execute", _boom)

    assert client.get("/healthz").status_code == 200

    resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.get_json()["database"] == "unreachable"


# ------------------------------------------------- lectura de flags de entorno


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True),
        (" true ", True),
        ("0", False), ("false", False), ("no", False), ("", False),
        # El que motiva el helper: bool("false") es True en Python.
        ("False", False),
    ],
)
def test_flag_parses_container_strings(monkeypatch, raw, expected):
    monkeypatch.setenv("SOME_FLAG", raw)
    assert config._flag("SOME_FLAG") is expected


def test_flag_falls_back_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_FLAG", raising=False)
    assert config._flag("SOME_FLAG") is False
    assert config._flag("SOME_FLAG", default=True) is True


# --------------------------------------------------- dueño único del scheduler


def test_production_does_not_schedule_by_default():
    """Every gunicorn worker runs the factory. If this defaulted to on, four
    web workers would each hit Yahoo and write their own JobRun rows."""
    assert config.ProductionConfig.RUN_SCHEDULER is False


def test_development_still_schedules():
    assert config.DevelopmentConfig.RUN_SCHEDULER is True


def test_scheduler_stays_off_when_the_flag_is_off(monkeypatch):
    from src.extensions import scheduler

    monkeypatch.setattr(config.TestingConfig, "RUN_SCHEDULER", False)
    app = create_app("testing")

    assert app.config["RUN_SCHEDULER"] is False
    assert not scheduler.running


# ------------------------------------------------------------ confianza al proxy


def test_proxy_headers_are_ignored_by_default():
    """Without a proxy in front, trusting X-Forwarded-* would let any client
    forge its own scheme and host."""
    app = create_app("testing")

    assert not isinstance(app.wsgi_app, ProxyFix)


def test_proxy_headers_rebuild_the_public_url_when_trusted(monkeypatch):
    """The reason ProxyFix exists here: behind Cloudflare, Flask sees plain
    HTTP to an internal address, and the Google OAuth redirect_uri built from
    it earns a redirect_uri_mismatch."""
    monkeypatch.setattr(config.TestingConfig, "TRUST_PROXY_HEADERS", True)
    app = create_app("testing")

    assert isinstance(app.wsgi_app, ProxyFix)

    # Goes through app.wsgi_app — the only way ProxyFix actually runs, since
    # test_request_context builds its URL adapter without touching the
    # middleware stack.
    from flask import url_for

    app.add_url_rule(
        "/_test_external_url",
        "test_external_url",
        lambda: url_for("auth.google_callback", _external=True),
    )

    resp = app.test_client().get(
        "/_test_external_url",
        base_url="http://10.0.0.7:8000",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "truenorth.qevuno.com",
        },
    )

    assert resp.get_data(as_text=True) == (
        "https://truenorth.qevuno.com/auth/google/callback"
    )
