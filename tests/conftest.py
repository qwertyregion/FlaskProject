import sys
import os
import pytest
from pathlib import Path

# Гарантируем, что корень проекта в sys.path для импорта пакета app
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Устанавливаем переменные окружения для тестов
os.environ['FLASK_ENV'] = 'testing'
os.environ['FLASK_APP'] = 'run.py'


def pytest_configure(config):
    """Настройка маркеров pytest"""
    config.addinivalue_line("markers", "slow: медленные тесты (с time.sleep)")
    config.addinivalue_line("markers", "integration: интеграционные тесты с Redis")
    config.addinivalue_line("markers", "unit: быстрые юнит-тесты")


def pytest_collection_modifyitems(config, items):
    """Автоматически маркируем тесты по файлам"""
    import pytest
    
    for item in items:
        if "test_redis_state" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "test_websocket_validator" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Маркируем медленные тесты
        if "ttl" in item.name.lower():
            item.add_marker(pytest.mark.slow)


@pytest.fixture(scope="session")
def app():
    """Создает Flask приложение с TestingConfig для всех тестов"""
    from app import create_app
    from config import TestingConfig
    
    app = create_app(TestingConfig)
    
    with app.app_context():
        yield app


@pytest.fixture(scope="session")
def client(app):
    """Создает тестовый клиент для Flask приложения"""
    return app.test_client()


@pytest.fixture(scope="session")
def db(app):
    """Создает базу данных для тестов"""
    from app.extensions import db
    
    # Создаем все таблицы
    db.create_all()
    
    yield db
    
    # Очищаем после тестов
    db.drop_all()


