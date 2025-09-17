@echo off
echo Running tests with coverage report...
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

REM Проверяем наличие pytest-cov
echo Checking pytest-cov installation...
python -c "import pytest_cov" 2>nul
if %errorlevel% neq 0 (
    echo Installing pytest-cov...
    pip install pytest-cov
)

echo.
echo Starting tests with coverage...
echo ========================================
pytest --cov=app --cov-report=html --cov-report=term-missing -v

echo.
echo ========================================
echo Coverage report generated in htmlcov/index.html
echo Tests completed!
pause
