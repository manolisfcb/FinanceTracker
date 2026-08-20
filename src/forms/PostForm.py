from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

from src.models import POST_CATEGORY_LABELS
from src.services.community import MAX_BODY_LENGTH, MAX_COMMENT_LENGTH, MAX_TITLE_LENGTH


class PostForm(FlaskForm):
    title = StringField(
        'Título',
        validators=[DataRequired(message='El título es obligatorio.'),
                    Length(max=MAX_TITLE_LENGTH)],
    )
    body = TextAreaField(
        'Mensaje',
        validators=[DataRequired(message='El mensaje no puede estar vacío.'),
                    Length(max=MAX_BODY_LENGTH)],
    )
    category = SelectField(
        'Categoría',
        choices=[(category.value, label) for category, label in POST_CATEGORY_LABELS.items()],
        validators=[DataRequired()],
    )
    submit = SubmitField('Publicar')


class CommentForm(FlaskForm):
    body = TextAreaField(
        'Comentario',
        validators=[DataRequired(message='El comentario no puede estar vacío.'),
                    Length(max=MAX_COMMENT_LENGTH)],
    )
    submit = SubmitField('Comentar')
