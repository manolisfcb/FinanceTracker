import re

from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from src.extensions import db

# Usernames are the community's display handle and half of the login
# identifier, so they stay to a shape that reads unambiguously next to an
# email: letters, digits, dot, dash and underscore.
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,30}$")


class UserModel(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Nullable: an account created through Google never had a password of its
    # own. 255 rather than 80 because werkzeug's scrypt hashes run to ~162
    # characters — SQLite ignores the length, but Postgres will not.
    password = db.Column(db.String(255), nullable=True)
    # Google's stable subject id (the `sub` claim), not the email: a Google
    # account can change its address, and matching on email alone would hand
    # the account to whoever inherits the old one.
    google_id = db.Column(db.String(64), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)
    added_on = db.Column(db.DateTime, server_default=db.func.now())
    # Community moderation: an admin may soft-delete anyone's post or
    # comment. Granted out-of-band (there is no self-service path to it).
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        """False for a Google-only account rather than an exception.

        Without the guard, `check_password_hash(None, ...)` raises, and a
        login attempt against a Google account would 500 instead of failing
        the way a wrong password does.
        """
        if not self.password:
            return False
        return check_password_hash(self.password, password)

    @property
    def has_password(self):
        return bool(self.password)

    def __init__(self, username, email, password=None, google_id=None,
                 full_name=None, avatar_url=None):
        self.username = username
        self.email = email
        self.google_id = google_id
        self.full_name = full_name
        self.avatar_url = avatar_url
        if password:
            self.set_password(password)

    def __repr__(self):
        return '<User %r>' % self.username

    @classmethod
    def find_by_identifier(cls, identifier):
        """The account for a login field holding either a username or an email.

        Case-insensitive on both: someone who registered as "Manuel" and
        types "manuel" is the same person, and no mail server treats the
        address as case-sensitive either.
        """
        if not identifier:
            return None
        needle = identifier.strip().lower()
        if not needle:
            return None
        return cls.query.filter(
            db.or_(
                func.lower(cls.username) == needle,
                func.lower(cls.email) == needle,
            )
        ).first()

    @classmethod
    def find_by_email(cls, email):
        if not email:
            return None
        return cls.query.filter(func.lower(cls.email) == email.strip().lower()).first()

    @classmethod
    def find_by_username(cls, username):
        if not username:
            return None
        return cls.query.filter(func.lower(cls.username) == username.strip().lower()).first()

    @classmethod
    def available_username(cls, *candidates):
        """A free username derived from whatever Google gave us.

        Google supplies a display name and an email but no handle, so one is
        derived from them and suffixed until it is free. The fallback covers
        the case where nothing survives cleaning (a name written entirely in
        a script the pattern rejects).
        """
        for candidate in candidates:
            base = re.sub(r"[^A-Za-z0-9._-]", "", (candidate or "").strip().replace(" ", ""))[:24]
            if len(base) < 3:
                continue
            if cls.find_by_username(base) is None:
                return base
            for suffix in range(2, 1000):
                attempt = f"{base}{suffix}"
                if cls.find_by_username(attempt) is None:
                    return attempt
        for suffix in range(1, 100000):
            attempt = f"inversor{suffix}"
            if cls.find_by_username(attempt) is None:
                return attempt
        raise RuntimeError("No free username could be derived")

    def serialize(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'added_on': self.added_on
        }

    def save(self):
        db.session.add(self)
        db.session.commit()
