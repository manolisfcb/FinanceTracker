from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class UserModel(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    added_on = db.Column(db.DateTime, server_default=db.func.now())

    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.set_password(password)
    
    def __repr__(self):
        return '<User %r>' % self.username

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