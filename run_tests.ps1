# PowerShell script for running tests
Write-Host "Running Flask application tests..." -ForegroundColor Green
Write-Host ""

# Активируем виртуальное окружение
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "flask_venv\Scripts\Activate.ps1"

# Устанавливаем переменные окружения для тестов
Write-Host "Setting up test environment variables..." -ForegroundColor Yellow
$env:FLASK_ENV = "testing"
$env:SECRET_KEY = "test-secret-key"
$env:WEATHER_API_KEY = "test-api-key"
$env:REDIS_URL = "redis://localhost:6379/1"

Write-Host ""
Write-Host "Environment variables set:" -ForegroundColor Cyan
Write-Host "FLASK_ENV: $env:FLASK_ENV"
Write-Host "REDIS_URL: $env:REDIS_URL"
Write-Host ""

# Запускаем тесты
Write-Host "Starting tests..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Gray
pytest -v --tb=short

Write-Host ""
Write-Host "========================================" -ForegroundColor Gray
Write-Host "Tests completed!" -ForegroundColor Green
Read-Host "Press Enter to continue..."
