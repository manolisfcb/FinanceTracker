from flask import render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from src.models.Transaction import Category, TransactionModel
from src.utils.filter import filter_by_columns_ilike, get_totals

from .personal_finance import personal_finance_bp


@personal_finance_bp.route('/transactions_charts', methods=['GET'])
@login_required
def transactions_charts():
    # Recuperar filtros
    category = request.args.getlist('categories')
    date = request.args.get('date', '').strip()
    transaction_type = request.args.get('type', '').strip()

    # Construir la consulta
    query = TransactionModel.query.join(Category)

    # Aplicar filtros dinámicamente
    filters = [
        {'column': 'user_id', 'value': [current_user.id], 'model': TransactionModel},
        {'column': 'name', 'value': category, 'model': Category},
        {'column': 'date', 'value': [date], 'model': TransactionModel},
        {'column': 'type', 'value': [transaction_type], 'model': TransactionModel},
    ]
    query = query.filter(*filter_by_columns_ilike(filters))

    # Los dos agregados los hace la base. Antes esto traía cada transacción a
    # memoria para que pandas hiciera dos groupby — 150 MB de pandas+numpy en
    # la imagen para sumar dos columnas que Postgres ya sabe sumar.
    # `with_entities` deriva una consulta nueva, así que `query` sigue intacta
    # para el get_totals de más abajo.
    income_expense_rows = (
        query.with_entities(TransactionModel.type, func.sum(TransactionModel.amount))
        .group_by(TransactionModel.type)
        .order_by(TransactionModel.type)
        .all()
    )
    income_expense_labels = [row[0] for row in income_expense_rows]
    income_expense_data = [float(row[1] or 0) for row in income_expense_rows]

    category_rows = (
        query.with_entities(TransactionModel.category_id, func.sum(TransactionModel.amount))
        .group_by(TransactionModel.category_id)
        .order_by(TransactionModel.category_id)
        .all()
    )
    category_labels = [row[0] for row in category_rows]
    category_data = [float(row[1] or 0) for row in category_rows]

    # Preparar contexto
    context = {
        'income_expense_labels': income_expense_labels,
        'income_data': [
            amount if kind == 'income' else 0
            for kind, amount in zip(income_expense_labels, income_expense_data)
        ],
        'expense_data': [
            abs(amount) if kind == 'expense' else 0
            for kind, amount in zip(income_expense_labels, income_expense_data)
        ],
        'category_labels': category_labels,
        'category_data': category_data,
        'categories': Category.query.all(),
        'totals': get_totals(query),
    }

    # Renderizar con HTMX o completo
    if request.headers.get('HX-Request'):
        return render_template('transaction_chart.html', **context)
    return render_template('transactions_charts.html', **context)
