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
# @main_bp.route('/transactions', methods=['GET', 'POST'])
# @login_required
# def transactions():


    
@main_bp.route('/transactions', methods=['GET'])
@main_bp.route('/transactions', methods=['GET'])
def transactions():
    # Recuperar filtros enviados por el formulario
    category = request.args.get('category', '').strip()
    date = request.args.get('date', '').strip()
    transaction_type = request.args.get('type', '').strip()
    page = request.args.get('page', 1, type=int)  # Página actual, predeterminado: 1
    per_page = 20  # Número de elementos por página

    # Construir la consulta base
    query = TransactionModel.query.join(Category)

    # Aplicar filtros dinámicamente
    filters = []
    filters.append(TransactionModel.user_id == current_user.id)  # Filtra por usuario actual
    if category:
        filters.append(Category.name.ilike(f"%{category}%"))  # Filtra por nombre de categoría
    if date:
        filters.append(TransactionModel.date.ilike(f"%{date}%"))  # Filtra por fecha como texto
    if transaction_type:
        filters.append(TransactionModel.type.ilike(f"%{transaction_type}%"))  # Filtra por tipo de transacción

    # Aplicar todos los filtros
    query = query.filter(*filters)

    # Paginación
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    transactions = [transaction.serialize() for transaction in pagination.items]
    totals = get_totals(query)
    # Contexto para la plantilla
    context = {
        'transactions': transactions,
        'pagination': pagination,
        'totals': totals
    }

    # Renderizar la página con HTMX si se usa
    if request.headers.get('HX-Request'):
        return render_template('partials/transaction_table.html', **context)
    
    # Renderizar la página completa
    return render_template('transactions.html', **context)


## -- Upload transactions
@main_bp.route('/transactions/upload', methods=['GET', 'POST'])
def upload_transactions():
    if request.method == "POST":
        if not 'file' in request.files:
            flash('No file part', 'error')
            return redirect(url_for('main.upload_transactions'))
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            flash('Invalid file format, please upload a CSV file', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        
        bank_name = request.form['bank']
        if bank_name not in allowed_banks:
            flash('Invalid bank name', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        csv_file = TextIOWrapper(request.files['file'].stream, encoding='utf-8')
        
        
        csv_reader = csv.DictReader(csv_file)
        transactions = TransactionFactory(csv_reader, bank_name)
        try:
            transactions = transactions.create_transaction()
        except ValueError as e:
            flash(f'Error processing CSV file: {e}', 'error')
            return redirect(url_for('main.upload_transactions'))
        
        for transaction in transactions:
            transaction['user_id'] = current_user.id
            transaction_model = TransactionModel(**transaction)
            db.session.add(transaction_model)
        db.session.commit()
               
        flash('Transactions added successfully', 'success')
        return render_template('upload_transactions.html'), 200
    return render_template('upload_transactions.html'), 200


## -- Add transactions
@main_bp.route('/transactions/add', methods=['GET', 'POST'])
def add_transactions():
    if request.method == "POST":
        category = request.form['category']
        amount = request.form['amount']
        type = request.form['type'].lower()
        type = TransactionType.EXPENSE if type == 'expense' else TransactionType.INCOME
        description = request.form['description']
        date = request.form['date']
        date = datetime.strptime(date, '%Y-%m-%d')
        if date > datetime.now():
            flash('Invalid date, please select a date in the past or today', 'error')
            return redirect(url_for('main.add_transactions')) 
        
        category = Category.query.filter_by(name=category).first()
        if not category:
            category = Category(name=category)
            db.session.add(category)
            db.session.commit()
        
        transaction = {
            'category_id': category.id, 
            'user_id': current_user.id,
            'amount': amount,
            'type': type,
            'description': description,
            'date': date
            
        }
        print(transaction)
        transaction_model = TransactionModel(**transaction)
        db.session.add(transaction_model)
        db.session.commit()
        flash('Transaction added successfully', 'success')
        return redirect(url_for('main.transactions'))    
    return render_template('add_transaction.html'), 200

## -- Edit transactions
@main_bp.route('/transactions/edit/<int:id>', methods=['GET', 'PUT'])
def edit_transactions(id):
    if request.method == 'PUT':
        transaction = TransactionModel.query.get(id)
        if not transaction:
            return {'message': 'Transaction not found'}, 404
        
        
        data = request.form
        category = Category.query.filter_by(name=data['category']).first()
        if not category:
            category = Category(name=data['category'])
            db.session.add(category)
            db.session.commit()
        
        transaction.category_id = category.id
        transaction.amount = data['amount']
        transaction.type = data['type']
        transaction.description = data['description']
        transaction.date = data['date']
        
        db.session.commit()
        flash('Transaction updated successfully', 'success')
        return redirect(url_for('main.transactions'))
    else:
        transaction = TransactionModel.query.get(id)
        if not transaction:
            return {'message': 'Transaction not found'}, 404
        
        context = {
            'transaction': transaction.serialize()
        }
        return render_template('edit_transaction.html', **context), 200


@main_bp.route('/transactions/delete/<int:id>', methods=['DELETE'])
def delete_transactions(id):
    transaction = TransactionModel.query.get(id)
    if not transaction:
        return {'message': 'Transaction not found'}, 404
    
    db.session.delete(transaction)
    db.session.commit()
    
    response = '', 204  # Respuesta vacía con código 204
    response = make_response(response)
    response.headers['HX-Redirect'] = url_for('main.transactions')  # Redirigir a /transactions
    flash('Transaction deleted successfully', 'success')
    return response
