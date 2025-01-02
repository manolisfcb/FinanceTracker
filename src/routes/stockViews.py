from flask import  render_template, flash, redirect, url_for
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager

from flask import  render_template, request
from app import db
from src.models.Orders import OrderModel

from src.utils.filter import  get_totals
from app import htmx
from werkzeug.utils import secure_filename
from io import TextIOWrapper
import csv
from datetime import datetime
from src.resources.TransactionFactory import TransactionFactory, allowed_banks
from src.utils.filter import filter_by_columns_ilike
from src.forms import StockForm
from src.models.Stocks import StockModel

@main_bp.route('/stocks', methods=['GET'])
def get_stocks():
    form = StockForm()
    
    all_tickets = OrderModel.query.filter().all()
    tickets_list = [ticket.serialize() for ticket in all_tickets]
    context = {
        'tickets': tickets_list
    }
    if request.method == 'POST' and form.validate_on_submit():
        stock_name = form.stock_name.data
        stock_price = form.stock_price.data
        stock_quantity = form.stock_quantity.data
        buy_at = datetime.now()
        sell_at = None
        dividend_amount = None
        next_dividend_date = None
        next_dividend_amount = None
        data_com = None
        data_ex = None
        data_pag = None
        stock = StockModel(user_id=current_user.id, symbol=stock_name, quantity=stock_quantity, price=stock_price, buy_at=buy_at, sell_at=sell_at, dividend_amount=dividend_amount, next_dividend_date=next_dividend_date, next_dividend_amount=next_dividend_amount, data_com=data_com, data_ex=data_ex, data_pag=data_pag)
        try:
            db.session.add(stock)
            db.session.commit()

            flash(f'Stock {stock_name} added successfully!', 'success')
        except:
            flash(f'Error adding stock {stock_name}!', 'error')
        return redirect(url_for('main.portfolio'))
    return render_template('stocks/stocks.html', form=form, **context)
        


