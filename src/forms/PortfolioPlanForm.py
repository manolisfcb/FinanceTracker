from flask_wtf import FlaskForm
from wtforms import DecimalField, SubmitField
from wtforms.validators import InputRequired, NumberRange, Optional


class PortfolioPlanForm(FlaskForm):
    equity_etf_percent = DecimalField(
        'Acciones / ETF', validators=[InputRequired(), NumberRange(min=0, max=100)]
    )
    reit_percent = DecimalField(
        'REITs', validators=[InputRequired(), NumberRange(min=0, max=100)]
    )
    crypto_percent = DecimalField(
        'Cripto', validators=[InputRequired(), NumberRange(min=0, max=100)]
    )
    cash_percent = DecimalField(
        'Cash', validators=[InputRequired(), NumberRange(min=0, max=100)]
    )
    cash_balance_cad = DecimalField(
        'Cash actual (CAD)', validators=[Optional(), NumberRange(min=0)], default=0
    )
    submit = SubmitField('Guardar portafolio ideal')
