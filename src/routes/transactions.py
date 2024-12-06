from flask import Blueprint, render_template, flash, redirect, url_for
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
from src.forms.UserRegistratioForm import NamerForm
from src.forms.LoginForm import LoginForm
from flask import Blueprint, render_template, request
from app import db
from src.models.Transaction import TransactionModel, Category



@main_bp.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    transactions = TransactionModel.query.filter_by(user_id=current_user.id).order_by(TransactionModel.date.desc()).all()
    transactions = [transaction.serialize() for transaction in transactions]
    context = {
        'transactions': transactions
    }
    print(context)
    return render_template('transactions.html', **context)