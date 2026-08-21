import os
from dotenv import load_dotenv, find_dotenv
from sqlalchemy.pool import StaticPool

if os.path.exists('.env'):
    load_dotenv(find_dotenv())


def _flag(name, default=False):
    """Read a boolean from the environment.

    Containers pass everything as strings, and `bool("false")` is True — the
    kind of bug that only shows up as "why are the jobs running twice in
    production".
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config(object):
    DEBUG = False
    TESTING = False
    # caminhos padrão
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_PATH = os.path.join(BASE_PATH, 'output')
    TEMPLATES_PATH = os.path.join(BASE_PATH, 'src/templates')
    STATICS_PATH = os.path.join(BASE_PATH, 'src/static')
    SCHEDULER_API_ENABLED = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # yahoo (yfinance, free/MVP) today; swappable to eodhd|fmp later without
    # touching the domain — see src/services/market_data.
    MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "yahoo")
    # A new holding should have a value on its first portfolio view rather
    # than wait for the next 15-minute quote job.
    REFRESH_QUOTE_ON_ORDER_CREATE = True
    # The static universe is a fast search cache. Exact North American stock
    # and ETF tickers missing from it may be validated and added on demand.
    DISCOVER_UNKNOWN_ASSETS_ON_ORDER_CREATE = True
    # SEC's fair access policy requires a User-Agent naming the app and a
    # contact email, or EDGAR returns 403.
    SEC_EDGAR_USER_AGENT = os.getenv(
        "SEC_EDGAR_USER_AGENT", "TrueNorth Analytics mmedinac26@gmail.com"
    )
    # News sources to aggregate (comma-separated): yahoo, google. Both are
    # free and keyless. Reuters has no free API — deliberately not included.
    NEWS_PROVIDERS = os.getenv("NEWS_PROVIDERS", "yahoo,google")
    # Honour X-Forwarded-* from the reverse proxy. Behind Cloudflare (or any
    # TLS terminator) Flask otherwise sees a plain HTTP request to an
    # internal host, and every url_for(_external=True) — the Google OAuth
    # redirect_uri above all — comes out wrong. Off by default: with no proxy
    # in front, trusting these headers lets any client forge its own scheme
    # and host.
    TRUST_PROXY_HEADERS = _flag("TRUST_PROXY_HEADERS")
    # Which process owns the APScheduler jobs. Every gunicorn worker runs the
    # app factory, so leaving this on everywhere means N workers hitting
    # Yahoo N times and writing N duplicate JobRun rows. Exactly one process
    # should have it.
    RUN_SCHEDULER = _flag("RUN_SCHEDULER", default=True)
    # Google sign-in. Optional: without both values the button is hidden and
    # /auth/google says the feature is off, so a checkout with no Google
    # project still runs with password login.
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    # OpenID Connect discovery: Authlib reads the authorize/token/jwks
    # endpoints from here rather than us pinning URLs that Google rotates.
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    HOST = os.getenv("HOST")
    PORT = os.getenv("PORT")
    ENV = os.getenv("ENV")
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///finance.db")
    # Dev-only fallbacks so `flask run` works without a .env — never used in
    # production, where SECRET_KEY/JWT_SECRET_KEY below fail fast if unset.
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-insecure-jwt-key')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-secret-key')

    ROUTING_KEY = 'file_unzip_only'


class ProductionConfig(Config):
    DEVELOPMENT = False
    DEBUG = False
    # Opt-in in production: the web containers must not schedule anything,
    # only the dedicated worker does.
    RUN_SCHEDULER = _flag("RUN_SCHEDULER", default=False)
    # url_for(_external=True) builds https:// links even before ProxyFix has
    # a request to inspect (CLI commands, error pages).
    PREFERRED_URL_SCHEME = "https"
    HOST = os.getenv("HOST")
    PORT = os.getenv("PORT")
    ENV = os.getenv("ENV")
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    # No fallback here — create_app() checks these are actually set and
    # fails startup rather than run production with a guessable secret.
    # (A `os.environ[...]` default-less lookup right in this class body
    # would raise on every import of this module, including in dev/test,
    # since Python evaluates all class bodies when the module is imported.)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    SECRET_KEY = os.environ.get('SECRET_KEY')

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    HOST = os.getenv("HOST")
    PORT = os.getenv("PORT")
    ENV = os.getenv("ENV")
    ROUTING_KEY = 'file_unzip_only'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    JWT_SECRET_KEY = 'testing-jwt-key'
    SECRET_KEY = 'testing-secret-key'
    WTF_CSRF_ENABLED = False
    # Tests use explicit provider mocks; never let a form POST reach Yahoo.
    REFRESH_QUOTE_ON_ORDER_CREATE = False
    # Hermetic regardless of the developer's .env: a machine with real Google
    # credentials must not make the auth tests take a different branch.
    GOOGLE_CLIENT_ID = None
    GOOGLE_CLIENT_SECRET = None
    DISCOVER_UNKNOWN_ASSETS_ON_ORDER_CREATE = False
    # In-memory SQLite is per-connection — without a single shared
    # connection, tables created via db.create_all() are invisible to the
    # next request's connection.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': StaticPool,
        'connect_args': {'check_same_thread': False},
    }
