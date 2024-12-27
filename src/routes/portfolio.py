from flask import  render_template, flash, redirect, url_for, make_response
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager

from flask import  render_template, request
from app import db
from src.models.Transaction import TransactionModel, Category, TransactionType
from src.utils.filter import  get_totals
from app import htmx
from werkzeug.utils import secure_filename
from io import TextIOWrapper
import csv
from datetime import datetime
from src.resources.TransactionFactory import TransactionFactory, allowed_banks
from src.utils.filter import filter_by_columns_ilike


@main_bp.route('/portfolio', methods=['GET'])
#@login_required
def portfolio():
  # Datos mockeados para el portafolio
    portfolio = [
        {
            'name': 'BBSE3',
            'price': 36.01,
            'quantity': 12,
            'value': 432.12,
            'cost': 371.718,
            'avg_price': 30.98,
            'profit': 108.25,
            'percent_return': '16.25%',
            'percent_return_dividends': '29.12%'
        },
        {
            'name': 'AGRO3',
            'price': 22.56,
            'quantity': 25,
            'value': 564.00,
            'cost': 628.499,
            'avg_price': 25.14,
            'profit': 100.10,
            'percent_return': '-10.26%',
            'percent_return_dividends': '15.93%'
        },
        {
            'name': 'EGE3',
            'price': 35.58,
            'quantity': 20,
            'value': 711.60,
            'cost': 800.724,
            'avg_price': 40.04,
            'profit': -56.00,
            'percent_return': '-11.13%',
            'percent_return_dividends': '-6.99%'
        },
        {
            'name': 'ABCB4',
            'price': 20.67,
            'quantity': 45,
            'value': 930.15,
            'cost': 822.761,
            'avg_price': 18.28,
            'profit': 165.76,
            'percent_return': '13.05%',
            'percent_return_dividends': '20.15%'
        },
    ]

    # Datos mockeados para el rendimiento histórico
    performance_dates = ['2022-01', '2022-02', '2022-03', '2022-04', '2022-05']
    performance_values = [1000, 1500, 2000, 1800, 2200]

    # Datos mockeados para las contribuciones mensuales
    contribution_dates = ['2022-01', '2022-02', '2022-03', '2022-04', '2022-05']
    contribution_values = [500, 600, 800, 700, 1000]

    # Contexto para pasar al template
    context = {
        'portfolio': portfolio,
        'performance_dates': performance_dates,
        'performance_values': performance_values,
        'contribution_dates': contribution_dates,
        'contribution_values': contribution_values,
    }

    return render_template('portfolio.html', **context)
