from flask import render_template, request
from .personal_finance import personal_finance_bp
from flask_login import login_required, current_user
from src.models.Transaction import TransactionModel, Category
from src.utils.filter import filter_by_columns_ilike, get_totals
import pandas as pd


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
    
    # Serializar las transacciones y convertir a DataFrame
    transactions = [transaction.serialize() for transaction in query.all()]
    df = pd.DataFrame(transactions, columns=['type', 'amount', 'category_id'])

    # Preparar datos para el gráfico de ingresos vs gastos
    income_expense_group = df.groupby('type')['amount'].sum().reset_index()
    income_expense_labels = income_expense_group['type'].tolist()
    income_expense_data = income_expense_group['amount'].tolist()

    # Preparar datos para el gráfico de composición por categorías
    category_group = df.groupby('category_id')['amount'].sum().reset_index()
    category_labels = category_group['category_id'].tolist()
    category_data = category_group['amount'].tolist()

    # Preparar contexto
    context = {
        'income_expense_labels': income_expense_labels,
        'income_data': [amount if type == 'income' else 0 for type, amount in zip(income_expense_labels, income_expense_data)],
        'expense_data': [abs(amount) if type == 'expense' else 0 for type, amount in zip(income_expense_labels, income_expense_data)],
        'category_labels': category_labels,
        'category_data': category_data,
        'categories': Category.query.all(),
        'totals': get_totals(query),
    }

    # Renderizar con HTMX o completo
    if request.headers.get('HX-Request'):
        return render_template('transaction_chart.html', **context)
    return render_template('transactions_charts.html', **context)
