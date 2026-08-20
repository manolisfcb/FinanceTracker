from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class AllocationTargetForm(FlaskForm):
    asset_symbol = StringField('Activo', validators=[DataRequired()])
    target_percent = StringField('% objetivo', validators=[DataRequired()])
    submit = SubmitField('Guardar')
