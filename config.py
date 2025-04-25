import os
from dotenv import load_dotenv, find_dotenv

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
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'xxx')  # Replace with a secure key for production
    SECRET_KEY = os.environ.get('SECRET_KEY', 'xxx')  # Replace with a secure key for production
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
    FLASK_DEBUG=1



    ROUTING_KEY = 'file_unzip_only'


class ProductionConfig(Config):
    DEVELOPMENT = False
    DEBUG = False
    HOST = os.getenv("HOST")
    PORT = os.getenv("PORT")
    ENV = os.getenv("ENV")
    TESTING = False

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    HOST = os.getenv("HOST")
    PORT = os.getenv("PORT")
    ENV = os.getenv("ENV")
    ROUTING_KEY = 'file_unzip_only'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = True
