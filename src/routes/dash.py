from flask import Blueprint, render_template
from .main import main_bp
from flask_login import login_required

@main_bp.route('/dash', methods=['GET'])
# @login_required
def dash_page():
    
    context = {
    "totals": {
        "performance": 8.42,
        "patrimonio": 48167.85,
        "costo_adquisicion": 52933.97,
        "proventos_acumulados": 8656.30,
        "lucro_operaciones": 567.90,
        "total_contribuicoes": 57506.18
    },
    "historical_labels": ["12/23", "01/24", "02/24", "03/24", "04/24"],
    "historical_data": [17.75, 15.40, 13.20, 12.00, 10.50],
    "contributions_labels": ["2022-05", "2022-06", "2022-07"],
    "contributions_data": [12000, 3000, 5000],
    "portfolio_labels": ["Acciones", "Fondos", "Efectivo"],
    "portfolio_data": [50, 30, 20]
}
    return render_template('dash.html', **context)