from flask import Blueprint, render_template, flash, redirect, url_for
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
from src.forms.UserRegistratioForm import NamerForm
from src.forms.LoginForm import LoginForm
from flask import Blueprint, render_template, request
from app import db
from src.models.Transaction import TransactionModel, Category
from sqlalchemy import or_
from src.utils.filter import filter
from sqlalchemy.orm import joinedload


# @main_bp.route('/transactions', methods=['GET', 'POST'])
# @login_required
# def transactions():
    
@main_bp.route('/transactions', methods=['GET'])
def transactions():
    # Recuperar filtros enviados por el formulario
    category = request.args.get('category', '').strip()
    date = request.args.get('date', '').strip()
    transaction_type = request.args.get('type', '').strip()

    print(request.args)
    print(category)
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

    # Obtener los resultados
    transactions = query.options(joinedload(TransactionModel.category)).all()

    # # Renderizar los resultados
    # return render_template("partials/transaction_table.html", transactions=transactions)

    transactions = [transaction.serialize() for transaction in query]
    context = {
        'transactions': transactions
    }
    print(context)
    
    if request.headers.get('HX-Request'):
        return render_template('partials/transaction_table.html', **context)
    
    return render_template('transactions.html', **context)
