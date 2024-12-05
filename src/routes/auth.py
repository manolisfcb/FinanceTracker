from flask import Blueprint, render_template, flash
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
from src.forms.UserRegistratioForm import NamerForm
from flask import Blueprint, render_template, request

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
        flash(f'Account created for {name}!', 'success')
        return render_template('register.html', name=name, form=form)

    # Maneja solicitudes GET (muestra el formulario inicialmente)
    return render_template('register.html', name=None, form=form)



@main_bp.route('/login', methods=['GET'])
def login():
    return render_template('login.html')