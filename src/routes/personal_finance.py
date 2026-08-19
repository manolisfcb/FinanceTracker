from flask import Blueprint

personal_finance_bp = Blueprint('personal_finance', __name__)

# Views are attached to this blueprint from dash.py, transactions.py and
# transactions_charts.py — kept as separate files since each already covers
# a distinct screen, but grouped under one blueprint/endpoint namespace.
