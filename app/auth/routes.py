from flask import Blueprint, redirect, url_for, flash, render_template, current_app, request
from flask_login import login_user, login_required, logout_user
from typing import Union
from .forms import LoginForm, RegistrationForm
from ..models import User
from app.extensions import db, limiter
import time

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Ограничиваем попытки входа
def login() -> Union[str, redirect]:
    """
    Представление обрабатывающее 'GET' и 'POST' запросы на логирование пользователя
    """
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        # Защита от timing атак - всегда выполняем проверку пароля
        if user:
            password_valid = user.check_password(form.password.data)
        else:
            # Имитируем проверку пароля для несуществующего пользователя
            User().check_password(form.password.data)
            password_valid = False
        
        if user and password_valid:
            login_user(user, remember=form.remember_me.data)
            current_app.logger.info(f"Successful login: {user.email} from {request.remote_addr}")
            return redirect(url_for('main.index'))
        else:
            current_app.logger.warning(f"Failed login attempt: {form.email.data} from {request.remote_addr}")
            flash('Неверный email или пароль', 'danger')
    
    return render_template('login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")  # Ограничиваем регистрацию
def register() -> Union[str, redirect]:
    """
    Представление обрабатывающее 'GET' и 'POST' запросы на регистрацию пользователя
    """
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        
        # Проверяем, существует ли пользователь
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            current_app.logger.warning(f"Registration attempt with existing credentials: {email} from {request.remote_addr}")
            flash('Пользователь с таким email или username уже существует', category='info')
            return redirect(url_for('auth.register'))
        
        # Создаем нового пользователя
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        current_app.logger.info(f"New user registered: {email} from {request.remote_addr}")
        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)


# @app_flask.route('/logout', methods=['GET', ])
@auth_bp.route('/logout', methods=['GET', ])
@login_required
def logout() -> redirect:
    """
    Представление обрабатывающее 'GET' запрос на выход пользователя
    """
    logout_user()
    return redirect(url_for('main.index'))


@auth_bp.before_request
def check_request() -> Union[None, tuple]:
    """Проверяет разрешенные HTTP методы"""
    if request.method not in ['GET', 'POST', 'PUT', 'DELETE']:
        return "Bad request", 400
    return None

