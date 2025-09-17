@echo off
echo Starting Flask application in development mode...
set FLASK_ENV=development
set SECRET_KEY=dev-secret-key-change-in-production
set WEATHER_API_KEY=6d34cbca51f9ba973d3b9945d85a90fe
python run.py
