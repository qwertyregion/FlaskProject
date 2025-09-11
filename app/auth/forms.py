from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, BooleanField, StringField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Regexp
from app.models import User
import re


class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')


class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[
        DataRequired(),
        Length(min=5, max=20, message='имя должно быть не менее пяти и не более двадцати символов'),
        Regexp('^[a-zA-Z0-9_]+$', message='Имя пользователя может содержать только буквы, цифры и подчеркивания')
    ])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[
        DataRequired(),
        Length(min=8, max=128, message='Пароль должен быть от 8 до 128 символов'),
        Regexp('^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]', 
               message='Пароль должен содержать минимум: 1 строчную букву, 1 заглавную букву, 1 цифру и 1 специальный символ')
    ])
    confirm_password = PasswordField('Подтвердите пароль', validators=[
        DataRequired(),
        EqualTo('password', message='Пароли должны совпадать')
    ])
    
    def validate_password(self, field):
        """Дополнительная валидация пароля"""
        password = field.data
        
        # Проверка на слабые пароли
        weak_passwords = [
            'password', '123456', '123456789', 'qwerty', 'abc123', 
            'password123', 'admin', 'letmein', 'welcome', 'monkey'
        ]
        
        if password.lower() in weak_passwords:
            raise ValidationError('Этот пароль слишком простой. Выберите более сложный пароль.')
        
        # Проверка на повторяющиеся символы
        if len(set(password)) < 4:
            raise ValidationError('Пароль должен содержать разнообразные символы.')
        
        # Проверка на последовательности
        if any(password[i:i+3] in 'abcdefghijklmnopqrstuvwxyz' or 
               password[i:i+3] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or
               password[i:i+3] in '0123456789' for i in range(len(password)-2)):
            raise ValidationError('Пароль не должен содержать последовательные символы.')


