from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

class Stock(FlaskForm):
    ticket = StringField('Ticket', validators=[DataRequired()])
    quantity = StringField('Quantity', validators=[DataRequired()])
    price = StringField('Price', validators=[DataRequired()])
    date = StringField('Date', validators=[DataRequired()])
    submit = SubmitField('Submit')
    
