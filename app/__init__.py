import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, request, Blueprint, send_from_directory, current_app
from flask_migrate import Migrate

from app.extensions import db, login_manager, socketio, limiter, talisman, redis_client
from app.websocket import register_socketio_handlers


def create_app(config_class='config.Config'):
    app = Flask(__name__)
    app.static_folder = os.path.abspath('app/static')
    app.config.from_object(config_class)

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    migrate = Migrate(app, db)
    
    # Инициализация безопасности
    limiter.init_app(app)
    talisman.init_app(app, 
                     force_https=False,  # True в продакшене
                     strict_transport_security=True,
                     strict_transport_security_max_age=31536000,
                     content_security_policy={
                         'default-src': "'self'",
                         'script-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
                         'style-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
                         'img-src': ["'self'", "data:", "https://openweathermap.org"],
                         'connect-src': ["'self'", "https://api.openweathermap.org", "https://ipapi.co"]
                     })

    # Импортируем модели ПОСЛЕ инициализации
    from app import models

    # Регистрация Blueprints
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.chat.routes import chat_bp
    app.register_blueprint(auth_bp)   #url_prefix='/auth'
    app.register_blueprint(main_bp)     #, url_prefix='/main'
    app.register_blueprint(chat_bp)
    
    # Регистрация API контроллеров
    from app.controllers import MessageController, RoomController, UserController
    message_controller = MessageController()
    room_controller = RoomController()
    user_controller = UserController()
    app.register_blueprint(message_controller.bp)
    app.register_blueprint(room_controller.bp)
    app.register_blueprint(user_controller.bp)

    # Инициализация Redis клиента (если доступен)
    redis_url = app.config.get('REDIS_URL')
    if redis_url:
        try:
            import redis as _redis
            # decode_responses=True -> строки, а не bytes
            client = _redis.from_url(redis_url, decode_responses=True)
            # тест соединения
            client.ping()
            # присваиваем в расширение
            from app import extensions as _ext
            _ext.redis_client = client
            app.logger.info(f"Redis подключен: {redis_url}")
        except Exception as e:
            app.logger.warning(f"Не удалось подключиться к Redis по {redis_url}: {e}")

    # Инициализация Socket IO ПОСЛЕ регистрации Blueprints
    message_queue = None
    if redis_client is not None:
        # Используем Redis как бэкенд для межпроцессной коммуникации
        message_queue = app.config.get('REDIS_URL')

    socketio.init_app(app,
                      cors_allowed_origins=["http://localhost:5000", "http://127.0.0.1:5000"],
                      logger=False,  # Включите для отладки
                      engineio_logger=False,
                      ping_timeout=30,
                      ping_interval=10,
                      message_queue=message_queue
                      )
    register_socketio_handlers(socketio)

    # Импорт sockets больше не нужен - используется websocket модуль
    from app.error_handlers import register_error_handlers

    # Регистрируем безопасные обработчики ошибок
    register_error_handlers(app)

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

    # Настройка логирования безопасности
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/security.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Security logging started')

    @app.before_request
    def log_request():
        # Логируем только подозрительные запросы
        if request.method in ['POST', 'PUT', 'DELETE']:
            app.logger.info(f"Security: {request.method} {request.path} from {request.remote_addr}")

    # Создаем таблицы при первом запуске
    with app.app_context():
        db.create_all()
    return app


