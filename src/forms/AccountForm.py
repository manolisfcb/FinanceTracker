from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional

from src.models import ACCOUNT_TYPE_LABELS


class AccountForm(FlaskForm):
    type = SelectField(
        'Tipo de cuenta',
        choices=[(account_type.value, label) for account_type, label in ACCOUNT_TYPE_LABELS.items()],
        validators=[DataRequired()],
    )
    name = StringField('Nombre', validators=[DataRequired()])
    broker = StringField('Broker', validators=[Optional()])
    submit = SubmitField('Guardar')
