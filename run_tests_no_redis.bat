@echo off
echo Running Flask application tests (without Redis)...
echo.

REM Активируем виртуальное окружение
echo Activating virtual environment...
call flask_venv\Scripts\activate.bat

REM Устанавливаем переменные окружения для тестов (без Redis)
echo Setting up test environment variables...
set FLASK_ENV=testing
set SECRET_KEY=test-secret-key
set WEATHER_API_KEY=test-api-key

echo.
echo Environment variables set:
echo FLASK_ENV=%FLASK_ENV%
echo REDIS_URL=not_set_(using_memory_fallback)
echo.

REM Запускаем тесты (Redis тесты будут пропущены)
echo Starting tests...
echo ========================================
pytest -v --tb=short

echo.
echo ========================================
echo Tests completed! (Redis tests skipped)
pause
