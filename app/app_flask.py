
from flask import render_template, redirect, url_for, flash, Flask
from flask_login import login_user, logout_user, login_required, LoginManager, UserMixin
from forms import LoginForm, RegistrationForm
from models import User  # Ваша модель пользователя


app = Flask(__name__)
app.secret_key = '323j4244j4k46l43l55n3'  # Обязательно добавьте секретный ключ!

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


# Заглушка для модели пользователя
# class User(UserMixin):
#     pass


@login_manager.user_loader
def load_user(user_id):
    return User()  # В реальном приложении здесь должна быть загрузка пользователя из БД


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(url_for('index'))
        flash('Неверный email или пароль', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
# ----------------------------------------------------------------------


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return 'about'


@app.route('/contact')
def contact():
    return 'contact'


if __name__ == "__main__":
    app.run(debug=True)
