from flask import Blueprint, render_template
from .main import main_bp

@main_bp.route('/register', methods=['GET'])
def register():
    return render_template('register.html')


@main_bp.route('/login', methods=['GET'])
def login():
    return render_template('login.html')