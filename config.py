import os
from dotenv import load_dotenv, find_dotenv
from sqlalchemy.pool import StaticPool

if os.path.exists('.env'):
    load_dotenv(find_dotenv())


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
    # In-memory SQLite is per-connection — without a single shared
    # connection, tables created via db.create_all() are invisible to the
    # next request's connection.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': StaticPool,
        'connect_args': {'check_same_thread': False},
    }
