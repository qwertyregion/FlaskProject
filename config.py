import os
import secrets

# Безопасный API ключ (в продакшене должен быть в переменных окружения)
# ВНИМАНИЕ: Замените на ваш реальный API ключ в переменных окружения!
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', '6d34cbca51f9ba973d3b9945d85a90fe')


class Config:
    # Версия приложения
    VERSION = os.environ.get('APP_VERSION', '1.0.0')
    
    # Безопасная генерация SECRET_KEY
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    
    # Конфигурация базы данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(__file__), 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CSRF защита
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 час
    
    # Настройки сессий
    PERMANENT_SESSION_LIFETIME = 3600  # 1 час
    SESSION_COOKIE_SECURE = False  # True в продакшене с HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Настройки безопасности
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB максимум
    MESSAGE_MAX_LENGTH = 1000  # Максимальная длина сообщения
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    
    # Логирование
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Внешние API
    WEATHER_API_KEY = WEATHER_API_KEY

    # Redis URL (используется для SocketIO message_queue и state managers)
    REDIS_URL = os.environ.get('REDIS_URL')


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # False для разработки (HTTP)
    SESSION_COOKIE_SAMESITE = 'Lax'  # Более мягкие настройки для разработки


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Обязательно True для HTTPS
    SESSION_COOKIE_SAMESITE = 'Strict'  # Строгие настройки для продакшена
    SESSION_COOKIE_HTTPONLY = True  # Защита от XSS
    
    # В продакшене используем более строгие настройки
    WTF_CSRF_TIME_LIMIT = 1800  # 30 минут
    
    # Дополнительные настройки безопасности для продакшена
    PREFERRED_URL_SCHEME = 'https'  # Принудительное использование HTTPS
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB максимум в продакшене


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Конфигурация по умолчанию
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
