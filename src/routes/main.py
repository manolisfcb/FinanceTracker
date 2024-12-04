from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__, url_prefix='/')

@main_bp.route('/', methods=['GET'])
def home_page():
    return render_template('index.html')