import sys
from pathlib import Path

# Гарантируем, что корень проекта в sys.path для импорта пакета app
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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


