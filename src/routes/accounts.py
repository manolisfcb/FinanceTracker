from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.forms.AccountForm import AccountForm
from src.models import Account, AccountType, OrderModel
from src.routes.portfolio import portfolio_bp


@portfolio_bp.route('/accounts', methods=['GET'])
@login_required
def list_accounts():
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name.asc()).all()
    form = AccountForm()
    return render_template('accounts.html', accounts=accounts, form=form)


@portfolio_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_account():
    form = AccountForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        if Account.query.filter_by(user_id=current_user.id, name=name).first():
            flash('Ya existe una cuenta con ese nombre', 'error')
            return render_template('add_account.html', form=form, editing=False)
        account = Account(
            user_id=current_user.id,
            type=AccountType(form.type.data),
            name=name,
            broker=(form.broker.data or '').strip() or None,
        )
        db.session.add(account)
        db.session.commit()
        flash('Cuenta creada correctamente', 'success')
        return redirect(url_for('portfolio.list_accounts'))
    return render_template('add_account.html', form=form, editing=False)


@portfolio_bp.route('/accounts/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    account = Account.query.filter_by(id=id, user_id=current_user.id).first()
    if account is None:
        abort(404)

    form = AccountForm(obj=account)
    if form.validate_on_submit():
        name = form.name.data.strip()
        duplicate = (
            Account.query
            .filter(
                Account.user_id == current_user.id,
                Account.name == name,
                Account.id != account.id,
            )
            .first()
        )
        if duplicate is not None:
            flash('Ya existe una cuenta con ese nombre', 'error')
            return render_template('add_account.html', form=form, editing=True)

        account.type = AccountType(form.type.data)
        account.name = name
        account.broker = (form.broker.data or '').strip() or None
        db.session.commit()
        flash('Cuenta actualizada correctamente', 'success')
        return redirect(url_for('portfolio.list_accounts'))

    if request.method == 'GET':
        form.type.data = account.type.value
    return render_template('add_account.html', form=form, editing=True)


@portfolio_bp.route('/accounts/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_account(id):
    account = Account.query.filter_by(id=id, user_id=current_user.id).first()
    if not account:
        return {'message': 'Account not found'}, 404

    if OrderModel.query.filter_by(account_id=account.id).first():
        flash('No se puede eliminar una cuenta con órdenes registradas', 'error')
        return '', 400

    db.session.delete(account)
    db.session.commit()
    flash('Cuenta eliminada', 'success')
    return '', 204
