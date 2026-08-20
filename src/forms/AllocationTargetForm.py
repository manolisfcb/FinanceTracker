from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired


class AllocationTargetForm(FlaskForm):
    # Choices are filled by the route with the sectors the portfolio actually
    # holds: a free-typed sector would never match `Asset.sector` and the
    # target would silently apply to nothing.
    sector = SelectField('Sector', validators=[DataRequired()], choices=[])
    target_percent = StringField('% objetivo', validators=[DataRequired()])
    submit = SubmitField('Guardar')
