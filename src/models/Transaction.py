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
    
    def __repr__(self):
        return f"<Category(name={self.name}"

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

    
    def serialize(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': round(self.amount, 2),
            'type': self.type.value,
            'category_id': self.category.name if self.category else None,
            'description': self.description,
            'date': self.date
        }
        
    
    def get_total_amount(user_id):
        return TransactionModel.query.filter_by(user_id=user_id).with_entities(db.func.sum(TransactionModel.amount)).scalar() or 0.0
    
    def get_total_income(user_id):
        return TransactionModel.query.filter_by(user_id=user_id, type=TransactionType.INCOME).with_entities(db.func.sum(TransactionModel.amount)).scalar() or 0.0
    
    def get_total_expense(user_id):
        return TransactionModel.query.filter_by(user_id=user_id, type=TransactionType.EXPENSE).with_entities(db.func.sum(TransactionModel.amount)).scalar() or 0.0
