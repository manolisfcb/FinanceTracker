from flask import Blueprint, render_template, flash, redirect, url_for, make_response
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
import plotly.express as px
from flask import Blueprint, render_template, request
from app import db
from src.models.Transaction import TransactionModel, Category, TransactionType
from sqlalchemy import or_, and_, case, func
from src.utils.filter import filter, get_totals
from app import htmx
from werkzeug.utils import secure_filename
from src.resources.charting import plot_income_expense_bar_char
from io import TextIOWrapper
import csv
from datetime import datetime
import pandas as pd
from src.resources.TransactionFactory import TransactionFactory, allowed_banks
from src.utils.filter import filter_by_columns_ilike
# @main_bp.route('/transactions', methods=['GET', 'POST'])
# @login_required
# def transactions():

@main_bp.route('/transactions_charts', methods=['GET'])
def transactions_charts():
    
    category = request.args.get('category', '').strip()
    date = request.args.get('date', '').strip()
    transaction_type = request.args.get('type', '').strip()
        # Aplicar filtros dinámicamente
    
    filterss=[
        {'column': 'user_id', 'value': current_user.id, 'model': TransactionModel},
        {'column': 'name', 'value': category, 'model': Category},
        {'column': 'date', 'value': date, 'model': TransactionModel},
        {'column': 'type', 'value': transaction_type, 'model': TransactionType}
    ]
    
    filters = filter_by_columns_ilike(filterss)
    query = TransactionModel.query.join(Category)
    query = query.filter(*filters)
    transactions = query.all()    
    transactions = [transaction.serialize() for transaction in transactions]
    df = pd.DataFrame(transactions)
    
    bar_chart = plot_income_expense_bar_char(df)
    
    context = {
        'bar_chart': bar_chart.to_html(),
        'transactions': df.to_dict(orient='records'),
        'totals': get_totals(query)
    }
    
        # Renderizar la página con HTMX si se usa
    if request.headers.get('HX-Request'):
        return render_template('partials/transaction_chart.html', **context)
    return render_template('transactions_charts.html', **context)
