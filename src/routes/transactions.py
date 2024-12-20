from flask import Blueprint, render_template, flash, redirect, url_for
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
from src.forms.UserRegistratioForm import NamerForm
from src.forms.LoginForm import LoginForm
from flask import Blueprint, render_template, request
from app import db
from src.models.Transaction import TransactionModel, Category, TransactionType
from sqlalchemy import or_, and_, case, func
from src.utils.filter import filter, get_totals
from sqlalchemy.orm import joinedload
from app import htmx
from sqlalchemy import text


# @main_bp.route('/transactions', methods=['GET', 'POST'])
# @login_required
# def transactions():


    
@main_bp.route('/transactions', methods=['GET'])
def transactions():
    # Recuperar filtros enviados por el formulario
    category = request.args.get('category', '').strip()
    date = request.args.get('date', '').strip()
    transaction_type = request.args.get('type', '').strip()


    query = TransactionModel.query.join(Category)
    
    
  # Aplicar filtros dinámicamente
    filters = []
    if category:
        filters.append(Category.name.ilike(f"%{category}%"))  # Filtra por nombre de categoría
    if date:
        filters.append(TransactionModel.date.ilike(f"%{date}%"))  # Filtra por fecha como texto
    if transaction_type:
        filters.append(TransactionModel.type.ilike(f"%{transaction_type}%"))  # Filtra por tipo de transacción

    # Aplicar todos los filtros
    query = query.filter(*filters)
   

    totals = get_totals(query)

    transactions = [transaction.serialize() for transaction in query]
    context = {
        'transactions': transactions,
        "totals": totals,
    }
    
    if htmx:
        return render_template('partials/transaction_table.html', **context, htmx=htmx), 200    
    return render_template('transactions.html', **context), 200
