import os
import logging
from flask_migrate import Migrate
from app.extensions import db
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from app.__init__ import socketio, create_app
from app.middleware.security import SecurityMiddleware, RateLimitMiddleware

# Загружаем переменные окружения из .env файла если он существует
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Определяем окружение
environment = os.environ.get('FLASK_ENV', 'development')

# Создаем приложение с правильной конфигурацией
if environment == 'production':
    from config import ProductionConfig
    app_flask = create_app(ProductionConfig)
else:
    from config import DevelopmentConfig
    app_flask = create_app(DevelopmentConfig)

# Инициализируем middleware безопасности
security_middleware = SecurityMiddleware(app_flask)
rate_limit_middleware = RateLimitMiddleware(app_flask)

# Настройка логирования
if environment == 'production':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )

if __name__ == "__main__":
    if environment == 'production':
        # Продакшен настройки
        socketio.run(
            app_flask,
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=False,
            use_reloader=False
        )
    else:
        # Разработка настройки
        socketio.run(
            app_flask,
            host='127.0.0.1',
            debug=True,
            port=5000,
        )

