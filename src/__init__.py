import os

import flask
from flask_login import current_user
from flask_restful import Api

from src.extensions import db, migration, jwt, login_manager, htmx, scheduler

MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

WEEKDAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Screener figures are in each asset's own reporting currency, so the column
# mixes markets and the symbol is what tells them apart.
CURRENCY_SYMBOLS = {"CAD": "C$", "USD": "US$", "BRL": "R$"}

CONFIG_MAP = {
    "development": "config.DevelopmentConfig",
    "production": "config.ProductionConfig",
    "testing": "config.TestingConfig",
}


def _is_reloader_parent(app) -> bool:
    """Whether this process is the watcher half of Werkzeug's auto-reloader.

    With `debug=True`, `app.run()` re-executes the entrypoint in a child
    process, so `create_app()` runs twice — once in the watcher, once in the
    process actually serving. Without this guard both start a scheduler and
    every job runs twice: duplicate provider calls, duplicate JobRun rows,
    and SQLite lock contention between the two.

    The watcher sets WERKZEUG_RUN_MAIN=true in the child, so an unset value
    while in debug means "this is the watcher". A debug run with the reloader
    off (`flask run --no-reload`, the project's VS Code config) also lands
    here and gets no scheduler — jobs firing mid-debug-session are rarely
    what you want anyway.
    """
    return app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"


def create_app(config_name=None):
    app = flask.Flask(__name__)

    config_name = config_name or os.getenv("ENV", "development")
    app.config.from_object(CONFIG_MAP[config_name])

    if config_name == "production" and not (app.config.get("SECRET_KEY") and app.config.get("JWT_SECRET_KEY")):
        raise RuntimeError(
            "SECRET_KEY and JWT_SECRET_KEY must be set in the environment when ENV=production."
        )

    app.template_folder = app.config["TEMPLATES_PATH"]
    app.static_folder = app.config["STATICS_PATH"]
    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["version"] = "0.0.1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/doc"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger_ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    db.init_app(app)
    migration.init_app(app, db)
    jwt.init_app(app)
    login_manager.init_app(app)
    htmx.init_app(app)

    # Import models so their mappers register with SQLAlchemy before any
    # request or `flask db migrate` run.
    from src.models import UserModel

    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return UserModel.query.get(user_id)

    from src.routes.main import main_bp
    from src.routes.auth import auth_bp
    from src.routes.portfolio import portfolio_bp
    from src.routes.stockViews import stocks_bp
    from src.routes.personal_finance import personal_finance_bp
    from src.routes.dividends import dividends_bp
    from src.routes.inbox import inbox_bp, unread_inbox_count
    from src.routes.tools import tools_bp

    # Importing these registers their view functions onto the blueprints
    # above (decorator side effects) — the imports themselves are unused.
    from src.routes import dash  # noqa: F401
    from src.routes import orders  # noqa: F401
    from src.routes import accounts  # noqa: F401
    from src.routes import transactions  # noqa: F401
    from src.routes import transactions_charts  # noqa: F401

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(personal_finance_bp)
    app.register_blueprint(dividends_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(tools_bp)

    @app.context_processor
    def inject_unread_inbox_count():
        if not current_user.is_authenticated:
            return {}
        return {"unread_inbox_count": unread_inbox_count(current_user.id)}

    api = Api(app)
    from src.routes import stockResources

    api.add_resource(stockResources.StockResources, "/api/stock")

    @app.template_filter("currency")
    def format_currency_filter(value):
        if value is None:
            return "0.00"
        return f"{value:,.2f}"

    @app.template_filter("ratio")
    def format_ratio_filter(value):
        """Plain 2-decimal number for nullable indicators (P/E, P/B, D/E...)
        — unlike `currency`, None renders as '—' rather than '0.00', since a
        missing indicator is not the same as an actual zero."""
        if value is None:
            return "—"
        return f"{value:,.2f}"

    @app.template_filter("percent")
    def format_percent_filter(value):
        """yfinance exposes yields/margins/payout as 0-1 fractions."""
        if value is None:
            return "—"
        return f"{value * 100:.2f}%"

    @app.template_filter("date_es")
    def format_date_es_filter(value):
        if value is None:
            return "—"
        return f"{value.day} de {MONTHS_ES[value.month - 1]}"

    @app.template_filter("date_long_es")
    def format_date_long_es_filter(value):
        """Full date with weekday, for the dashboard subtitle."""
        if value is None:
            return "—"
        return (
            f"{WEEKDAYS_ES[value.weekday()]}, {value.day} de "
            f"{MONTHS_ES[value.month - 1]} {value.year}"
        )

    @app.template_filter("month_abbr_es")
    def format_month_abbr_es_filter(value):
        if value is None:
            return "—"
        return MONTHS_ES[value.month - 1][:3]

    @app.template_filter("quantity")
    def format_quantity_filter(value):
        """Share counts without trailing zeros.

        Equities such as 0.2254 keep their four decimals, while crypto can
        retain up to eight; whole quantities still render as whole numbers.
        """
        if value is None:
            return "—"
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.8f}".rstrip("0").rstrip(".")

    @app.template_filter("fx")
    def format_fx_filter(value):
        """FX rates need four decimals — at two, USDCAD 1.3642 and 1.3598
        both read as 1.36 and the CAD totals stop reconciling."""
        return "—" if value is None else f"{value:,.4f}"

    @app.template_filter("domain")
    def format_domain_filter(value):
        """Bare hostname of a URL — a full https://www.… doesn't fit the
        narrow key-stats column and reads as noise next to a label."""
        if not value:
            return "—"
        host = value.split("://")[-1].split("/")[0]
        return host[4:] if host.startswith("www.") else host

    @app.template_filter("currency_symbol")
    def format_currency_symbol_filter(value):
        """C$, US$… for a currency code. An unknown code falls back to the
        code itself rather than to nothing — an unlabelled number in a column
        that mixes CAD and USD is worse than an ugly one."""
        if not value:
            return ""
        return CURRENCY_SYMBOLS.get(value, f"{value} ")

    @app.template_filter("compact_number")
    def format_compact_number_filter(value):
        if value is None:
            return "—"
        for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(value) >= threshold:
                return f"{value / threshold:,.2f}{suffix}"
        return f"{value:,.2f}"

    # The scheduler hits market data providers on an interval — keep it out
    # of tests so test runs stay hermetic and fast, and so repeated
    # create_app("testing") calls don't fail trying to start an
    # already-running APScheduler.
    if not app.testing and not _is_reloader_parent(app):
        scheduler.init_app(app)
        from src.resources.jobs import refresh_fundamentals  # noqa: F401
        from src.resources.jobs import refresh_quotes  # noqa: F401
        from src.resources.jobs import refresh_fx  # noqa: F401
        from src.resources.jobs import refresh_snapshots  # noqa: F401
        from src.resources.jobs import refresh_dividends  # noqa: F401
        from src.resources.jobs import refresh_filings  # noqa: F401
        from src.resources.jobs import refresh_news  # noqa: F401

        if not scheduler.running:
            scheduler.start()

    return app
