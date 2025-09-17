@echo off
echo Running Flask application tests...
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

REM Запускаем тесты
echo Starting tests...
echo ========================================
pytest -v --tb=short

echo.
echo ========================================
echo Tests completed!
pause
