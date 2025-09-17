@echo off
echo Running Redis-specific tests...
echo.

REM Активируем виртуальное окружение
echo Activating virtual environment...
call flask_venv\Scripts\activate.bat

REM Устанавливаем переменные окружения для тестов
echo Setting up test environment variables...
set FLASK_ENV=testing
set SECRET_KEY=test-secret-key
set WEATHER_API_KEY=test-api-key
set REDIS_URL=redis://localhost:6379/1

echo.
echo Environment variables set:
echo FLASK_ENV=%FLASK_ENV%
echo REDIS_URL=%REDIS_URL%
echo.

REM Проверяем доступность Redis
echo Checking Redis connection...
python -c "import redis; r = redis.from_url('redis://localhost:6379/1'); print('Redis ping:', r.ping())"
if %errorlevel% neq 0 (
    echo ERROR: Redis is not available!
    echo Please make sure Redis is installed and running.
    pause
    exit /b 1
)

echo.
echo Redis is available. Starting Redis tests...
echo ========================================
pytest tests/test_redis_state.py -v --tb=short

echo.
echo ========================================
echo Redis tests completed!
pause
