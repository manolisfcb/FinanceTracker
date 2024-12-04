import flask 
from flask import request, jsonify
from flask import render_template
import dotenv
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager



db = SQLAlchemy()
migration = Migrate()
ENVIROMENT = os.getenv("ENV")

env = {
    "development": "config.DevelopmentConfig",
    "production": "config.ProductionConfig",
    "testing": "config.TestingConfig"
}

# Create the application instance and load the configuration
app = flask.Flask(__name__)
app.config.from_object(ENVIROMENT)
app.template_folder = app.config['TEMPLATES_PATH']
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["DEBUG"] = True
app.config["version"] = "0.0.1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/doc"
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger_ui"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"


jwt = JWTManager(app)


from src.routes import main
from src.routes import auth


app.register_blueprint(main.main_bp)



db.init_app(app)
migration.init_app(app, db)

def create_app():
    app = flask.Flask(__name__)
    app.config.from_object(env[ENVIROMENT])
    app.template_folder = app.config['TEMPLATES_PATH']
    app.config["DEBUG"] = True
    return app

from src.models import UserModel

if __name__ == '__main__':
    app.run(debug=True)