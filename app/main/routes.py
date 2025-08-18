from datetime import datetime
from flask import Blueprint, render_template, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app.external_api import get_location_data, get_weather_data
from app.main.forms import ProfileUserForm
from app.models import User, Message
from app.schemas import GeoWeatherResponse
from app.extensions import db, socketio
from config import apikey

main_bp = Blueprint('main', __name__)


@main_bp.route('/',  methods=['GET', ])
# @app_flask.route('/', methods=['GET', ])
@login_required  # Теперь страница требует аутентификации
def index():
    """
    Представление отображающее hostname сервиса
    """
    try:
        location_data = get_location_data()
        print(location_data)
        weather_data = get_weather_data(lat=location_data.latitude, lon=location_data.longitude, key=apikey, )
        print(weather_data)
        response = GeoWeatherResponse(
            location=location_data,
            weather=weather_data,
            timestamp=int(datetime.now().timestamp())
        )
        return render_template(template_name_or_list='index.html',
                               location=response.location,
                               weather=response.weather,
                               timestamp=response.timestamp)
    except Exception as e:
        return render_template('error.html', error=str(e))


# @app_flask.route('/profile/<username>', methods=['GET', 'POST', ])
@main_bp.route('/profile/<username>', methods=['GET', 'POST', ])
@login_required
def profile(username):
    """
        Представление отображающее профиль пользователя
    """
    form = ProfileUserForm(obj=current_user)  # Автозаполнение формы
    if form.validate_on_submit():
        changes = False
        if current_user.username != form.username.data:
            current_user.username = form.username.data
            changes = True
        if current_user.email != form.email.data:
            current_user.email = form.email.data
            changes = True
        if changes:
            db.session.commit()  # Один запрос для всех изменений
            flash('Ваш профиль обновлен!', 'success')
            return redirect(url_for('main.profile', username=current_user.username))
    data = {
        'username': current_user.username,
        'id': current_user.id,
        'email': current_user.email,
        'password_hash': current_user.password_hash,
    }
    return render_template('profile.html', data=data, form=form, )


# @app_flask.route('/about', methods=['GET', ])
@main_bp.route('/about', methods=['GET', ])
@login_required
def about():
    """
        Представление отображающее страницу about
    """
    return render_template('about.html')


# @app_flask.route('/contact', methods=['GET', ])
@main_bp.route('/contact', methods=['GET', ])
@login_required
def contact():
    """
        Представление отображающее страницу contact
    """
    return render_template('contact.html')


@main_bp.errorhandler(400)
@main_bp.errorhandler(401)
@main_bp.errorhandler(403)
@main_bp.errorhandler(404)
@main_bp.errorhandler(405)
def handel_4xx_error(error):
    """
        обработчик 400-х исключений
    """
    return render_template(template_name_or_list='handel_4xx_error.html',
                           error_code=error.code,
                           error_name=error.name,
                           error_description=error.description
                           ), error.code