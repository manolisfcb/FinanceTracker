"""Sign-in, sign-up and Google OAuth.

Two ways in, one account: a password against a username *or* an email, or
Google. Registration logs the new account in and drops it on the dashboard —
there is no confirmation step and no bounce back to the login form.
"""

from urllib.parse import urlparse

from authlib.integrations.base_client import OAuthError
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from src.extensions import db, oauth
from src.forms.LoginForm import LoginForm
from src.forms.UserRegistratioForm import RegisterForm
from src.models.UserModel import UserModel

auth_bp = Blueprint('auth', __name__)

# Where a session lands when there is no `next` to honour. The dashboard, not
# the landing page: someone who just signed in wants their portfolio.
HOME_ENDPOINT = 'portfolio.dash_page'

# Survives the round trip to Google, which cannot carry our `?next=`.
OAUTH_NEXT_KEY = 'oauth_next'


def _safe_next(target):
    """A `?next=` value restricted to paths inside this site.

    An absolute URL here turns the login form into an open redirect: a
    phishing page sends someone through our real login and lands them on a
    lookalike that asks for the password again.
    """
    if not target:
        return None
    if not target.startswith('/') or target.startswith('//') or '\\' in target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    return target


def _destination():
    return _safe_next(request.args.get('next')) or url_for(HOME_ENDPOINT)


def _google_client():
    """The registered Google client, or None when this deployment has none.

    Credentials are optional: without them the templates hide the button and
    the two OAuth routes say so rather than raising.
    """
    if not current_app.config.get('GOOGLE_CLIENT_ID'):
        return None
    return oauth.create_client('google')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(HOME_ENDPOINT))

    form = RegisterForm()
    if form.validate_on_submit():
        user = UserModel(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            password=form.password.data,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:
            # The form already checked both uniques; this is the race where
            # two registrations for the same handle commit at once.
            db.session.rollback()
            current_app.logger.exception('Registration failed for %s', form.email.data)
            flash('No pudimos crear la cuenta. Probá de nuevo.', 'danger')
            return render_template('register.html', form=form)

        login_user(user, remember=True)
        flash(f'¡Bienvenido, {user.username}! Tu cuenta ya está lista.', 'success')
        return redirect(_destination())

    return render_template('register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(HOME_ENDPOINT))

    form = LoginForm()
    if form.validate_on_submit():
        user = UserModel.find_by_identifier(form.identifier.data)
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(_destination())

        # One message for both "no such user" and "wrong password": telling
        # them apart lets anyone probe which emails have accounts here.
        if user is not None and not user.has_password:
            flash('Esa cuenta se creó con Google. Entrá con el botón de Google.', 'info')
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Cerraste sesión.', 'success')
    return redirect(url_for('main.home_page'))


@auth_bp.route('/auth/google')
def google_login():
    client = _google_client()
    if client is None:
        flash('El acceso con Google no está configurado en este servidor.', 'info')
        return redirect(url_for('auth.login'))

    # Google cannot carry our `?next=`, so it waits in the session for the
    # callback — same round trip Authlib already uses for state and nonce.
    session[OAUTH_NEXT_KEY] = _safe_next(request.args.get('next'))
    return client.authorize_redirect(url_for('auth.google_callback', _external=True))


@auth_bp.route('/auth/google/callback')
def google_callback():
    client = _google_client()
    if client is None:
        flash('El acceso con Google no está configurado en este servidor.', 'info')
        return redirect(url_for('auth.login'))

    target = _safe_next(session.pop(OAUTH_NEXT_KEY, None)) or url_for(HOME_ENDPOINT)

    try:
        token = client.authorize_access_token()
    except OAuthError as error:
        # Covers the ordinary case of someone pressing "Cancel" on Google's
        # consent screen as well as a state mismatch.
        current_app.logger.info('Google sign-in aborted: %s', error.error)
        flash('No se completó el acceso con Google.', 'info')
        return redirect(url_for('auth.login'))

    claims = token.get('userinfo') or {}
    if not claims:
        try:
            claims = client.userinfo(token=token)
        except Exception:
            current_app.logger.exception('Google userinfo lookup failed')
            claims = {}

    user, created = _resolve_google_user(claims)
    if user is None:
        flash('Google no nos dio un email verificado para esa cuenta. '
              'Podés registrarte con email y contraseña.', 'danger')
        return redirect(url_for('auth.register'))

    login_user(user, remember=True)
    if created:
        flash(f'¡Bienvenido, {user.username}! Tu cuenta ya está lista.', 'success')
    return redirect(target)


def _resolve_google_user(claims):
    """The account behind a set of Google claims, creating it if it is new.

    Returns `(user, created)`, or `(None, False)` when the claims are not
    good enough to identify anyone.
    """
    subject = (claims.get('sub') or '').strip()
    email = (claims.get('email') or '').strip().lower()
    if not subject or not email:
        return None, False

    user = UserModel.query.filter_by(google_id=subject).first()
    if user is not None:
        _refresh_google_profile(user, claims)
        db.session.commit()
        return user, False

    # `email_verified` is what stops someone from registering a Google
    # account against an address they do not own and inheriting the local
    # account that already uses it.
    if not claims.get('email_verified'):
        return None, False

    user = UserModel.find_by_email(email)
    if user is not None:
        user.google_id = subject
        _refresh_google_profile(user, claims)
        db.session.commit()
        return user, False

    user = UserModel(
        username=UserModel.available_username(
            claims.get('given_name'), claims.get('name'), email.split('@')[0]
        ),
        email=email,
        google_id=subject,
        full_name=claims.get('name'),
        avatar_url=claims.get('picture'),
    )
    db.session.add(user)
    db.session.commit()
    return user, True


def _refresh_google_profile(user, claims):
    """Keep the name and avatar current, but never overwrite them with nothing."""
    if claims.get('name'):
        user.full_name = claims['name']
    if claims.get('picture'):
        user.avatar_url = claims['picture']
