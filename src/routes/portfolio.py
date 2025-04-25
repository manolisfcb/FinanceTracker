from flask import  render_template, flash, redirect, url_for, make_response
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager

from flask import  render_template, request
from app import db
from src.models.Transaction import TransactionModel, Category, TransactionType
from src.models.Portfolio import PortfolioModel
from src.utils.filter import  get_totals
from app import htmx
from werkzeug.utils import secure_filename
from io import TextIOWrapper
import csv
import pandas as pd
from datetime import datetime
from src.resources.TransactionFactory import TransactionFactory, allowed_banks
from src.utils.filter import filter_by_columns_ilike
from src.models.Stocks import StockModel
from src.forms.StockForm import Stock
import yfinance as yf

@main_bp.route('/portfolio', methods=['GET'])
#@login_required
def portfolio():
  # Datos mockeados para el portafolio
    form = Stock()
    from src.utils.querys import get_portfolio
    # portfolio = PortfolioModel.query.all()
    # portfolio = [portfolio.serialize() for portfolio in portfolio]
    
    result = db.session.execute(get_portfolio(current_user.id)).fetchall()

    # Opcional: convertir a lista de dicts
    portfolio = [
        dict(row._mapping)  # _mapping es la forma correcta de transformar Row en dict
        for row in result
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
        'patrimony': 10000,
        'total_invested': 100000,
        # 'tickets': tickets
    }

    return render_template('portfolio.html', **context, form=form)


