# PowerShell script for running Redis-specific tests
Write-Host "Running Redis-specific tests..." -ForegroundColor Green
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

# Проверяем доступность Redis
Write-Host "Checking Redis connection..." -ForegroundColor Yellow
try {
    $redisCheck = python -c "import redis; r = redis.from_url('redis://localhost:6379/1'); print('Redis ping:', r.ping())"
    Write-Host $redisCheck -ForegroundColor Green
} catch {
    Write-Host "ERROR: Redis is not available!" -ForegroundColor Red
    Write-Host "Please make sure Redis is installed and running." -ForegroundColor Red
    Read-Host "Press Enter to continue..."
    exit 1
}

Write-Host ""
Write-Host "Redis is available. Starting Redis tests..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Gray
pytest tests/test_redis_state.py -v --tb=short

Write-Host ""
Write-Host "========================================" -ForegroundColor Gray
Write-Host "Redis tests completed!" -ForegroundColor Green
Read-Host "Press Enter to continue..."
