from flask import Blueprint, render_template, flash, redirect, url_for
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
from src.forms.UserRegistratioForm import NamerForm
from src.forms.LoginForm import LoginForm
from flask import Blueprint, render_template, request
from src.models.UserModel import UserModel
from app import db

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    name = None
    password = None
    email = None
    form = NamerForm()

    # Maneja solicitudes POST (cuando el formulario es enviado)
    if request.method == 'POST' and form.validate_on_submit():
        name = form.name.data
        password = form.password.data
        email = form.email.data
        form.name.data = ''  # Limpia el campo después de procesar
        
        
        new_user = UserModel(name, email, password)
        if UserModel.query.filter_by(email=email).first():
            flash(f'User with email {email} already exists!', 'error')
            return render_template('register.html', name=name, form=form)
        try:
            new_user.save()
        except:
            flash(f'Error creating account for {name}!', 'error')
            return render_template('register.html', name=name, form=form)
        
        flash(f'Account created for {name}!', 'success')
        return render_template('register.html', name=name, form=form)
    
    all_users = UserModel.query.all()
    all_users = [user.serialize() for user in all_users]    

    # Maneja solicitudes GET (muestra el formulario inicialmente)
    return render_template('register.html', name=None, form=form, users= all_users)


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = UserModel.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('main.home_page'))  # Redirige al home después de iniciar sesión
        else:
            flash('Invalid login', 'error')  # Mensaje si el login es inválido
    elif request.method == 'POST':  # Mensaje solo en intentos fallidos de inicio de sesión
        flash('Login to continue', 'info')
    return render_template('login.html', form=form)  # Muestra el formulario


@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('main.home_page'))  # Redirige al home después de cerrar sesión