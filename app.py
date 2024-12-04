import flask 
from flask import request, jsonify
from flask import render_template
import dotenv
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

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

app.config["DEBUG"] = True


@app.route('/', methods=['GET'])
def home():
    return "<h1>API</h1><p>This is an API for the project.</p>"


@app.route('/home', methods=['GET'])
def home_page():
    return render_template('index.html')

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