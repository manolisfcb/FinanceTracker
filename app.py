import flask 
from flask import request, jsonify
from flask import render_template
import dotenv
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_login import LoginManager
from flask_htmx import HTMX

app = flask.Flask(__name__)
db = SQLAlchemy()
migration = Migrate()
login_manager = LoginManager()
htmx = HTMX(app)

ENVIROMENT = os.getenv("ENV")

env = {
    "development": "config.DevelopmentConfig",
    "production": "config.ProductionConfig",
    "testing": "config.TestingConfig"
}
from src.models import UserModel, TransactionModel, Category

# Create the application instance and load the configuration
app.config.from_object(ENVIROMENT)
app.template_folder = app.config['TEMPLATES_PATH']
app.static_folder = app.config['STATICS_PATH']
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["DEBUG"] = True
app.config["version"] = "0.0.1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/doc"
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger_ui"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"


jwt = JWTManager(app)


from src.routes import main
from src.routes import auth, dash
from src.routes import transactions

app.register_blueprint(main.main_bp)



db.init_app(app)
migration.init_app(app, db)
login_manager.init_app(app)
login_manager.login_view = 'main.login'
@login_manager.user_loader
def load_user(user_id):
    return UserModel.query.get(user_id)

@app.template_filter('currency')
def format_currency_filter(value):
    if value is None:
        return "0.00"
    return f"{value:,.2f}"


def create_app():
    app = flask.Flask(__name__)
    app.config.from_object(env[ENVIROMENT])
    app.template_folder = app.config['TEMPLATES_PATH']
    app.config["DEBUG"] = True
    return app


if __name__ == '__main__':
    app.run(debug=True)