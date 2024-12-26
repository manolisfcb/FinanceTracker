from flask import Blueprint, render_template, flash, redirect, url_for, make_response
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager

from flask import Blueprint, render_template, request
from app import db
from src.models.Transaction import TransactionModel, Category, TransactionType
from sqlalchemy import or_, and_, case, func
from src.utils.filter import filter, get_totals
from app import htmx
from werkzeug.utils import secure_filename
from io import TextIOWrapper
import csv
from datetime import datetime
from src.resources.TransactionFactory import TransactionFactory, allowed_banks
# @main_bp.route('/transactions', methods=['GET', 'POST'])
# @login_required
# def transactions():

@main_bp.route('/transactions_charts', methods=['GET'])
def transactions_charts():
    return render_template('transactions_charts.html')