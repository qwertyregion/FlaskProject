from datetime import datetime
import requests
from flask import render_template, redirect, url_for, flash, jsonify, make_response, Blueprint
from flask import request as flask_request
from flask_login import login_user, logout_user, login_required, current_user
from app.__init__ import db
from app.__init__ import create_app
from app.schemas import GeolocationData, WeatherData, GeoWeatherResponse
from app.forms import LoginForm, RegistrationForm, ProfileUserForm
from app.models import User, load_user  # Ваша модель пользователя
from config import apikey

app_flask = create_app()
main_bp = Blueprint('main', __name__)

app_flask.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  # SQLite
app_flask.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


@app_flask.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    print(form.data)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for('index'))
        flash('Неверный email или пароль', 'danger')
    return render_template('login.html', form=form)


@app_flask.route('/register', methods=['GET', 'POST'])
def register():
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


@app_flask.route('/logout', methods=['GET', ])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
# ----------------------------------------------------------------------


@app_flask.route('/', methods=['GET', ])
@login_required  # Теперь страница требует аутентификации
def index():
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


@app_flask.route('/profile/<username>', methods=['GET', 'POST', ])
@login_required
def profile(username):
    form = ProfileUserForm(obj=current_user)  # Автозаполнение формы
    if form.validate_on_submit():
        changes_user, changes_email = False, False

        if current_user.username != form.username.data:
            current_user.username = form.username.data
            changes_user = True

        if current_user.email != form.email.data:
            current_user.email = form.email.data
            changes_email = True

        if changes_user or changes_email:
            db.session.commit()  # Один запрос для всех изменений
            flash('Ваш профиль обновлен!', 'success')
            return redirect(url_for('profile', username=current_user.username))

    data = {
        'username': current_user.username,
        'id': current_user.id,
        'email': current_user.email,
        'password_hash': current_user.password_hash,
    }
    return render_template('profile.html', data=data, form=form, )


@app_flask.route('/about', methods=['GET', ])
@login_required
def about():
    return render_template('about.html')


@app_flask.route('/contact', methods=['GET', ])
@login_required
def contact():
    return render_template('contact.html')


# -------------------------------------------------------------------------------------
def get_location_data() -> GeolocationData:
    """Определяет гео данные клиента по его IP"""
    headers = {
        'User-Agent': 'MyApp/1.0 (contact@myapp.com)',
        'Accept': 'application/json',
    }
    try:
        response = requests.get('https://ipapi.co/json/', headers=headers, ).json()
        # response.rises_for_status()
        return GeolocationData(
            ip=response['ip'],
            region=response['region'],
            city=response['city'],
            region_code=response['region_code'],
            country_capital=response['country_capital'],
            country_name=response['country_name'],
            postal=response['postal'],
            latitude=response['latitude'],
            longitude=response['longitude'],
            timezone=response['timezone'],
            currency_name=response['currency_name'],
            country_area=response['country_area'],
            country_population=response['country_population'],
            org=response['org'],
        )
    except requests.exceptions.RequestException as e:
        print(f"Ошибка геолокации: {e}")
        return GeolocationData()


def get_weather_data(lat: float, lon: float, key: str = apikey) -> WeatherData:
    """ Получает данные о погоде"""
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}""&lang='ru'&units=metric"
    try:
        response = requests.request(method='get', url=url, ).json()
        return WeatherData(
            description=response['weather'][0]['description'],
            icon=response['weather'][0]['icon'],
            main_temp=response['main']['temp'],
            main_pressure=response['main']['pressure'],
            main_humidity=response['main']['humidity'],
            visibility=response['visibility'],
            wind_speed=response['wind']['speed'],
            sys_sunrise=response['sys']['sunrise'],
            sys_sunset=response['sys']['sunset'],
            name=response['name'],
        )
    except Exception as e:
        print(f'не удалось получить данные погоды: {e}')
# ------------------------------------------------------------------------------------------------


@app_flask.errorhandler(400)
@app_flask.errorhandler(401)
@app_flask.errorhandler(403)
@app_flask.errorhandler(404)
@app_flask.errorhandler(405)
def handel_4xx_error(error):
    return render_template(template_name_or_list='handel_4xx_error.html',
                           error_code=error.code,
                           error_name=error.name,
                           error_description=error.description
                           ), error.code




if __name__ == "__main__":
    app_flask.run(debug=True)
