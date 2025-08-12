from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from app import app_flask

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'login'  # Указываем endpoint для страницы входа


def create_app(config_class='config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)

    # Обработчик для PUT-методов через скрытое поле _method
    @app.before_request
    def before_request():
        if request.form.get('_method') == 'PUT':
            request.environ['REQUEST_METHOD'] = 'PUT'

    # Импорт и регистрация blueprints/роутов
    # from app import app_flask
    # from app.app_flask import main_bp
    # app.register_blueprint(main_bp)

    # Импортируем модели после инициализации db
    # from app.models import User

    # Создаем таблицы при первом запуске
    with app.app_context():
        db.create_all()
    return app

