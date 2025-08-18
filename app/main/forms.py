from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Email, ValidationError
from app.models import User


class ProfileUserForm(FlaskForm):
    username = StringField(label="Введите новое имя пользователя",
                           validators=[
                               DataRequired(message="Поле обязательно для заполнения"),
                               Length(min=5, max=20, message='имя должно быть не менее пяти и не более двадцати символов', )],
                               # Regexp(regex='^[A-Za-z][A-Za-z0-9_.]*$', flags=0, message="Имя может содержать только буквы, цифры, точки и подчеркивания"),
                           description="Введите новое имя пользователя",
                           render_kw={
                               "class": "form-control",
                               "placeholder": "Ваше имя пользователя"
                           }
                           )
    email = StringField(label='Введите новое имя почты',
                        validators=[
                            DataRequired(message="Поле обязательно для заполнения"),
                            Email(message='Email должен быть валиден'),
                            Length(max=120), ],
                        description='Введите новое имя почты',
                        render_kw={
                            "class": "form-control",
                            "placeholder": "Ваше имя почты"
                        }
                        )

    # Проверяем, что имя почты не занято (кроме текущего пользователя)
    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if user and user.id != current_user.id:
            raise ValidationError("Этот почта уже используется")

    # Проверяем, что имя пользователя не занято (кроме текущего пользователя)
    def validate_username(self, field):
        user = User.query.filter_by(username=field.data).first()
        if user and user.id != current_user.id:
            raise ValidationError("Это имя пользователя уже занято")