from flask_wtf import FlaskForm
from wtforms import HiddenField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional


class ManualOrderForm(FlaskForm):
    account = SelectField('Cuenta', choices=[], validators=[DataRequired()])
    asset_symbol = StringField('Activo', validators=[DataRequired()])
    asset_id = HiddenField(validators=[Optional()])
    type = SelectField('Tipo', choices=[('BUY', 'Comprar'), ('SELL', 'Vender')], validators=[DataRequired()])
    quantity = StringField('Cantidad', validators=[DataRequired()])
    price = StringField('Precio', validators=[DataRequired()])
    fees = StringField('Comisiones', validators=[Optional()])
    currency = SelectField(
        'Moneda del precio',
        choices=[
            ('CAD', 'CAD — Dólar canadiense'),
            ('USD', 'USD — Dólar estadounidense'),
        ],
        default='CAD',
        validators=[DataRequired()],
    )
    executed_at = StringField('Fecha', validators=[DataRequired()])
    submit = SubmitField('Guardar orden')
