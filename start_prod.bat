@echo off
echo Starting Flask application in production mode...
echo WARNING: Make sure to set proper SECRET_KEY and other environment variables!
set FLASK_ENV=production
set SECRET_KEY=your-very-secure-production-secret-key-here
set WEATHER_API_KEY=your-production-weather-api-key
python run.py
pause
