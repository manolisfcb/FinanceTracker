from flask import Blueprint, render_template
from .main import main_bp
from flask_login import login_required

@main_bp.route('/dash', methods=['GET'])
@login_required
def dash_page():
    return render_template('dash.html')