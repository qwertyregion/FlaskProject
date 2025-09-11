# PowerShell script for development
Write-Host "Starting Flask application in development mode..." -ForegroundColor Green

$env:FLASK_ENV = "development"
$env:SECRET_KEY = "dev-secret-key-change-in-production"
$env:WEATHER_API_KEY = "6d34cbca51f9ba973d3b9945d85a90fe"

python run.py

Read-Host "Press Enter to continue..."
