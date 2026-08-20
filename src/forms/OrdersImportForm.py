from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired


class OrdersImportForm(FlaskForm):
    broker = SelectField(
        'Broker',
        choices=[('questrade', 'Questrade'), ('wealthsimple', 'Wealthsimple'), ('ibkr', 'Interactive Brokers')],
        validators=[DataRequired()],
    )
    account = SelectField('Cuenta destino', choices=[], validators=[DataRequired()])
    file = FileField('Archivo CSV', validators=[FileRequired(), FileAllowed(['csv'], 'Solo archivos CSV')])
    submit = SubmitField('Analizar archivo')
