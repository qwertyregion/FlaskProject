# Тестирование Flask приложения

## Доступные скрипты для запуска тестов

### Основные скрипты

#### 1. `run_tests.bat` / `run_tests.ps1`
**Запуск всех тестов с Redis**
- Активирует виртуальное окружение
- Устанавливает переменные окружения для тестов
- Запускает все тесты (включая Redis тесты)
- Требует запущенный Redis сервер

#### 2. `run_tests_no_redis.bat` / `run_tests_no_redis.ps1`
**Запуск тестов без Redis**
- Активирует виртуальное окружение
- Устанавливает переменные окружения для тестов
- Запускает тесты (Redis тесты будут пропущены)
- Использует in-memory fallback для Redis функций

#### 3. `run_redis_tests.bat` / `run_redis_tests.ps1`
**Запуск только Redis тестов**
- Проверяет доступность Redis
- Запускает только тесты из `tests/test_redis_state.py`
- Полезно для проверки Redis функциональности

#### 4. `run_tests_coverage.bat` / `run_tests_coverage.ps1`
**Запуск тестов с отчетом покрытия**
- Генерирует HTML отчет покрытия кода
- Показывает покрытие в терминале
- Создает файл `htmlcov/index.html` с детальным отчетом

## Переменные окружения для тестов

```bash
FLASK_ENV=testing
SECRET_KEY=test-secret-key
WEATHER_API_KEY=test-api-key
REDIS_URL=redis://localhost:6379/1  # Только для тестов с Redis
```

## Структура тестов

### Redis тесты (`tests/test_redis_state.py`)
- **63 теста** для проверки Redis функциональности
- Тестируют менеджеры состояния (UserStateManager, ConnectionManager, RoomManager)
- Проверяют TTL, валидацию данных, Unicode поддержку
- Требуют запущенный Redis сервер

### WebSocket валидатор тесты (`tests/test_websocket_validator.py`)
- **30 тестов** для проверки валидации WebSocket сообщений
- Тестируют валидацию сообщений, имен комнат, ID пользователей
- Проверяют защиту от XSS, спама, некорректных данных
- Не требуют Redis

## Требования

### Для всех тестов:
- Python 3.7+
- Виртуальное окружение `flask_venv`
- Установленные зависимости из `requirements.txt`

### Для Redis тестов:
- Установленный и запущенный Redis сервер
- Переменная окружения `REDIS_URL`

### Для тестов покрытия:
- `pytest-cov` (устанавливается автоматически)

## Быстрый старт

1. **Установите Redis** (если нужны Redis тесты):
   ```bash
   # Windows с Chocolatey
   choco install redis-64
   
   # Или скачайте с https://redis.io/download
   ```

2. **Запустите Redis сервер**:
   ```bash
   redis-server
   ```

3. **Запустите тесты**:
   ```bash
   # Все тесты с Redis
   run_tests.bat
   
   # Или без Redis
   run_tests_no_redis.bat
   ```

## Результаты тестирования

### Ожидаемые результаты:
- **93 теста** всего
- **63 Redis теста** (если Redis доступен)
- **30 WebSocket валидатор тестов**
- **0 ошибок** при правильной настройке

### Отчеты:
- Консольный вывод с результатами
- HTML отчет покрытия (при использовании coverage скриптов)
- Логи pytest в `.pytest_cache/`

## Устранение проблем

### Redis недоступен:
- Используйте `run_tests_no_redis.bat`
- Или установите Redis и запустите `redis-server`

### Ошибки импорта:
- Убедитесь, что виртуальное окружение активировано
- Проверьте установку зависимостей: `pip install -r requirements.txt`

### Проблемы с правами (PowerShell):
- Выполните: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
