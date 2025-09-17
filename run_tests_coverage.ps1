# PowerShell script for running tests with coverage
Write-Host "Running tests with coverage report..." -ForegroundColor Green
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

# Проверяем наличие pytest-cov
Write-Host "Checking pytest-cov installation..." -ForegroundColor Yellow
try {
    python -c "import pytest_cov" 2>$null
    Write-Host "pytest-cov is already installed" -ForegroundColor Green
} catch {
    Write-Host "Installing pytest-cov..." -ForegroundColor Yellow
    pip install pytest-cov
}

Write-Host ""
Write-Host "Starting tests with coverage..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Gray
pytest --cov=app --cov-report=html --cov-report=term-missing -v

Write-Host ""
Write-Host "========================================" -ForegroundColor Gray
Write-Host "Coverage report generated in htmlcov/index.html" -ForegroundColor Cyan
Write-Host "Tests completed!" -ForegroundColor Green
Read-Host "Press Enter to continue..."
