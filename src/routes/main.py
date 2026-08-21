from flask import Blueprint, Response, redirect, render_template, request, url_for
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


@main_bp.route('/robots.txt', methods=['GET'])
def robots_txt():
    """Crawler policy: index the public landing, never treat the API as pages."""
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: {url_for('main.sitemap_xml', _external=True)}\n"
    )
    response = Response(body, content_type='text/plain; charset=utf-8')
    response.cache_control.public = True
    response.cache_control.max_age = 86400
    return response


@main_bp.route('/sitemap.xml', methods=['GET'])
def sitemap_xml():
    """The landing page is the sole public, indexable product URL today."""
    home_url = url_for('main.home_page', _external=True)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{home_url}</loc><changefreq>weekly</changefreq></url>\n'
        '</urlset>\n'
    )
    response = Response(body, content_type='application/xml; charset=utf-8')
    response.cache_control.public = True
    response.cache_control.max_age = 86400
    return response


@main_bp.after_app_request
def protect_non_public_routes_from_indexing(response):
    """Keep account, portfolio, health and API responses out of search results."""
    public_endpoints = {
        'main.home_page',
        'main.robots_txt',
        'main.sitemap_xml',
        'static',
    }
    if request.endpoint not in public_endpoints:
        response.headers.setdefault('X-Robots-Tag', 'noindex, nofollow, noarchive')
    return response


@main_bp.route('/healthz', methods=['GET'])
def healthz():
    """Liveness: is this process alive and serving?

    Deliberately does NOT touch the database. The container healthcheck polls
    this every 30s, and Neon suspends its compute after a few idle minutes —
    a probe that queried the database would keep the compute awake around the
    clock and quietly burn the plan's compute hours. Restarting the container
    would not fix a database outage anyway, so liveness is the wrong place to
    ask about it.
    """
    return {'status': 'ok'}, 200


@main_bp.route('/readyz', methods=['GET'])
def readyz():
    """Readiness: can this process actually serve a request end to end?

    This one does hit the database, so point a load balancer at it — not the
    container healthcheck. Unauthenticated and free of user data.
    """
    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        return {'status': 'error', 'database': 'unreachable'}, 503
    return {'status': 'ok', 'database': 'ok'}, 200
