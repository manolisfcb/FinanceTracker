from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    """One identity field, not two.

    Asking "usuario o email" removes the guess of which one this account was
    registered with — the lookup in UserModel.find_by_identifier accepts
    either, case-insensitively.
    """

    identifier = StringField(
        'Usuario o email',
        validators=[DataRequired(message='Escribí tu usuario o tu email.')],
        render_kw={'autocomplete': 'username', 'autofocus': True,
                   'placeholder': 'manuel · o manuel@ejemplo.ca'},
    )
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired(message='Escribí tu contraseña.')],
        render_kw={'autocomplete': 'current-password'},
    )
    remember = BooleanField('Mantener la sesión iniciada', default=True)
    submit = SubmitField('Entrar')
