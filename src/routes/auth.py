from flask import Blueprint, render_template
from .main import main_bp
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager

@main_bp.route('/register', methods=['GET'])
def register():
    return render_template('register.html')


@main_bp.route('/login', methods=['GET'])
def login():
    return render_template('login.html')