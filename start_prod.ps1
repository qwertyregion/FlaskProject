# PowerShell script for production
Write-Host "Starting Flask application in production mode..." -ForegroundColor Yellow
Write-Host "WARNING: Make sure to set proper SECRET_KEY and other environment variables!" -ForegroundColor Red

$env:FLASK_ENV = "production"
$env:SECRET_KEY = "your-very-secure-production-secret-key-here"
$env:WEATHER_API_KEY = "your-production-weather-api-key"

python run.py

Read-Host "Press Enter to continue..."
