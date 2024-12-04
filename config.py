import os
from dotenv import load_dotenv, find_dotenv


class Config(object):
    DEBUG = False
    TESTING = False
    # caminhos padrão
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_PATH = os.path.join(BASE_PATH, 'output')
    TEMPLATES_PATH = os.path.join(BASE_PATH, 'app/templates')
    STATICS_PATH = os.path.join(BASE_PATH, 'app/static')
    
    SECRET_KEY = os.environ.get('SECRET_KEY', 'xxx')  # Replace with a secure key for production
    DEBUG = False
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = os.getenv("DEBUG")
    HOST = os.getenv("HOST")
    PORT = os.getenv("PORT")
    ENV = os.getenv("ENV")
    TESTING = False

    ROUTING_KEY = 'file_unzip_only'