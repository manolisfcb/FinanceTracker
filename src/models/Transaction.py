from flask_sqlalchemy import SQLAlchemy
from enum import Enum

from app import db
# Enum para TransactionType
class TransactionType(Enum):
    INCOME = 'income'
    EXPENSE = 'expense'

# Modelo Category
class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.Enum(TransactionType), nullable=False)
    
    def __repr__(self):
        return f"<Category(name={self.name}, type={self.type})>"

# Modelo TransactionModel
class TransactionModel(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.Enum(TransactionType), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)  # Relación con Category
    description = db.Column(db.String(120), nullable=False)
    date = db.Column(db.DateTime, server_default=db.func.now())
    
    # Relación para obtener la categoría asociada
    category = db.relationship('Category', backref='transactions', lazy=True)
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount}, type={self.type})>"
