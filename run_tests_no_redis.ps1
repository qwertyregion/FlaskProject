# PowerShell script for running tests without Redis
Write-Host "Running Flask application tests (without Redis)..." -ForegroundColor Green
Write-Host ""

# Активируем виртуальное окружение
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "flask_venv\Scripts\Activate.ps1"

# Устанавливаем переменные окружения для тестов (без Redis)
Write-Host "Setting up test environment variables..." -ForegroundColor Yellow
$env:FLASK_ENV = "testing"
$env:SECRET_KEY = "test-secret-key"
$env:WEATHER_API_KEY = "test-api-key"

Write-Host ""
Write-Host "Environment variables set:" -ForegroundColor Cyan
Write-Host "FLASK_ENV: $env:FLASK_ENV"
Write-Host "REDIS_URL: not_set_(using_memory_fallback)"
Write-Host ""

# Запускаем тесты (Redis тесты будут пропущены)
Write-Host "Starting tests..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Gray
pytest -v --tb=short

Write-Host ""
Write-Host "========================================" -ForegroundColor Gray
Write-Host "Tests completed! (Redis tests skipped)" -ForegroundColor Yellow
Read-Host "Press Enter to continue..."
