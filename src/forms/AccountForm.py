from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional


class AccountForm(FlaskForm):
    type = SelectField(
        'Tipo de cuenta',
        choices=[('TFSA', 'TFSA'), ('RRSP', 'RRSP'), ('FHSA', 'FHSA'), ('MARGIN', 'Margin'), ('CASH', 'Cash')],
        validators=[DataRequired()],
    )
    name = StringField('Nombre', validators=[DataRequired()])
    broker = StringField('Broker', validators=[Optional()])
    submit = SubmitField('Guardar')
