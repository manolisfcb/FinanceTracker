"""Flask extension instances, created without an app.

Kept separate from src/__init__.py so any module can import an extension
(e.g. `from src.extensions import db`) without triggering the app factory
and its blueprint/route imports — this is what breaks the circular import
between app.py and src/models/*.py.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_login import LoginManager
from flask_htmx import HTMX
from flask_apscheduler import APScheduler

db = SQLAlchemy()
migration = Migrate()
jwt = JWTManager()
login_manager = LoginManager()
htmx = HTMX()
scheduler = APScheduler()
