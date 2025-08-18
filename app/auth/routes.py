from flask import Blueprint, redirect, url_for, flash, render_template
from flask_login import login_user, login_required, logout_user
from .forms import LoginForm, RegistrationForm
from ..models import User
from flask import request as flask_request
from app.extensions import db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
# @app_flask.route('/login', methods=['GET', 'POST'])
def login():
    """
    Представление обрабатывающее 'GET' и 'POST' запросы на логирование пользователя
    """
    form = LoginForm()
    print(form.data)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for('main.index'))
        flash('Неверный email или пароль', 'danger')
    return render_template('login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
# @app_flask.route('/register', methods=['GET', 'POST'])
def register():
    """
    Представление обрабатывающее 'GET' и 'POST' запросы на регистрацию пользователя
    """
    form = RegistrationForm()
    if form.validate_on_submit():
        username = flask_request.form['username']
        email = flask_request.form['email']
        password = flask_request.form['password']
        # Проверяем, существует ли пользователь
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            flash('Пользователь с таким email или username уже существует', category='info')
            return redirect(url_for('register'))
        # Создаем нового пользователя
        user = User(username=username, email=email, )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


# @app_flask.route('/logout', methods=['GET', ])
@auth_bp.route('/logout', methods=['GET', ])
@login_required
def logout():
    """
    Представление обрабатывающее 'GET' запрос на выход пользователя
    """
    logout_user()
    return redirect(url_for('main.index'))


@auth_bp.before_request
def check_request():
    if flask_request.method not in ['GET', 'POST', 'PUT', 'DELETE']:
        return "Bad request", 400

