import os

from flask import Flask, request, Blueprint, send_from_directory
from flask_migrate import Migrate

from app.extensions import db, login_manager, socketio
import logging

from app.sockets import register_socketio_handlers


def create_app(config_class='config.Config'):
    app = Flask(__name__)
    app.static_folder = os.path.abspath('app/static')
    app.config.from_object(config_class)

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    migrate = Migrate(app, db)

    # Импортируем модели и сокеты ПОСЛЕ инициализации
    from app import models
    from app import sockets

    # Регистрация Blueprints
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.chat.routes import chat_bp
    app.register_blueprint(auth_bp)   #url_prefix='/auth'
    app.register_blueprint(main_bp)     #, url_prefix='/main'
    app.register_blueprint(chat_bp)

    # Инициализация Socke IO ПОСЛЕ регистрации Blueprints
    socketio.init_app(app)
    register_socketio_handlers(socketio)



    # Обработчик для PUT-методов через скрытое поле _method
    @app.before_request
    def handle_put():
        if request.form.get('_method') == 'PUT':
            request.environ['REQUEST_METHOD'] = 'PUT'

    # Явно разрешаем статические файлы
    @app.route('/static/<path:filename>')
    def static_files(filename):
        response = send_from_directory(app.static_folder, filename)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if filename.endswith('.css'):
            response.headers['Content-Type'] = 'text/css'
        return response

    @app.before_request
    def log_request():
        logging.debug(f"""
        → Incoming Request:
        Method: {request.method}
        Path: {request.path}
        IP: {request.remote_addr}
        User-Agent: {request.user_agent}
        Headers: {dict(request.headers)}
        """)

    # Создаем таблицы при первом запуске
    with app.app_context():
        db.create_all()
    return app


