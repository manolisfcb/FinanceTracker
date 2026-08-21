from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import text

from src.extensions import db

main_bp = Blueprint('main', __name__, url_prefix='/')


@main_bp.route('/', methods=['GET'])
def home_page():
    """The public landing page — or the dashboard, once you are signed in.

    A logged-in user arriving at "/" wants their portfolio, not the sales
    pitch; sending them through a welcome page they have to click past is
    exactly the friction the landing exists to remove for everyone else.
    """
    if current_user.is_authenticated:
        return redirect(url_for('portfolio.dash_page'))
    return render_template('landing.html')


@main_bp.route('/healthz', methods=['GET'])
def healthz():
    """Liveness/readiness probe for the container orchestrator.

    Touches the database because a web process that cannot reach Postgres is
    not actually ready, and returning 200 anyway just means the orchestrator
    sends it traffic it will fail to serve. Deliberately unauthenticated and
    free of any user data.
    """
    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        return {'status': 'error', 'database': 'unreachable'}, 503
    return {'status': 'ok', 'database': 'ok'}, 200
