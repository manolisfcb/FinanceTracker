from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp, ValidationError

from src.models.UserModel import USERNAME_RE, UserModel


class RegisterForm(FlaskForm):
    """Three fields and you are in.

    No password confirmation: the field has a show/hide toggle instead, which
    catches typos without making everyone type the password twice. No email
    confirmation step either — the account is usable the moment it exists.
    """

    username = StringField(
        'Usuario',
        validators=[
            DataRequired(message='Elegí un nombre de usuario.'),
            Regexp(
                USERNAME_RE,
                message='Entre 3 y 30 caracteres: letras, números, punto, guion o guion bajo.',
            ),
        ],
        render_kw={'autocomplete': 'username', 'autofocus': True,
                   'placeholder': 'manuel'},
    )
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Escribí tu email.'),
            Email(message='Ese email no parece válido.'),
            Length(max=120),
        ],
        render_kw={'autocomplete': 'email', 'placeholder': 'manuel@ejemplo.ca'},
    )
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='Elegí una contraseña.'),
            Length(min=8, max=128, message='Mínimo 8 caracteres.'),
        ],
        render_kw={'autocomplete': 'new-password', 'placeholder': 'Mínimo 8 caracteres'},
    )
    submit = SubmitField('Crear cuenta y entrar')

    # Field-level validation rather than a flash after the fact: "ese usuario
    # ya existe" belongs under the field it is about, with everything else the
    # person typed still in the form.
    def validate_username(self, field):
        if UserModel.find_by_username(field.data):
            raise ValidationError('Ese usuario ya está tomado.')

    def validate_email(self, field):
        if UserModel.find_by_email(field.data):
            raise ValidationError('Ya hay una cuenta con ese email. Iniciá sesión.')
