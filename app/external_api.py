import requests

from app.schemas import GeolocationData, WeatherData
from config import apikey


def get_location_data() -> GeolocationData:
    """Определяет гео данные клиента по его IP"""
    headers = {
        'User-Agent': 'MyApp/1.0 (contact@myapp.com)',
        'Accept': 'application/json',
    }
    try:
        response = requests.get('https://ipapi.co/json/', headers=headers, ).json()
        # response.rises_for_status()
        return GeolocationData(
            ip=response['ip'],
            region=response['region'],
            city=response['city'],
            region_code=response['region_code'],
            country_capital=response['country_capital'],
            country_name=response['country_name'],
            postal=response['postal'],
            latitude=response['latitude'],
            longitude=response['longitude'],
            timezone=response['timezone'],
            currency_name=response['currency_name'],
            country_area=response['country_area'],
            country_population=response['country_population'],
            org=response['org'],
        )
    except requests.exceptions.RequestException as e:
        print(f"Ошибка геолокации: {e}")
        return GeolocationData()


def get_weather_data(lat: float, lon: float, key: str = apikey) -> WeatherData:
    """ Получает данные о погоде"""
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}""&lang='ru'&units=metric"
    try:
        response = requests.request(method='get', url=url, ).json()
        return WeatherData(
            description=response['weather'][0]['description'],
            icon=response['weather'][0]['icon'],
            main_temp=response['main']['temp'],
            main_pressure=response['main']['pressure'],
            main_humidity=response['main']['humidity'],
            visibility=response['visibility'],
            wind_speed=response['wind']['speed'],
            sys_sunrise=response['sys']['sunrise'],
            sys_sunset=response['sys']['sunset'],
            name=response['name'],
        )
    except Exception as e:
        print(f'не удалось получить данные погоды: {e}')