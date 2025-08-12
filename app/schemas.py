from pydantic import BaseModel, Field
from typing import Optional


class GeolocationData(BaseModel):
    ip: str = Field(default='Неизвестно')
    region: str = Field(default="Неизвестно")
    city: str = Field(default="Неизвестно")
    region_code: str = Field(default="Неизвестно")
    country_capital: str = Field(default="Неизвестно")
    country_name: str = Field(default="Неизвестно")
    postal: str = Field(default="Неизвестно")
    latitude: float = Field(default=180)
    longitude: float = Field(default=180)
    timezone: str = Field(default="Неизвестно")
    currency_name: str = Field(default="Неизвестно")
    country_area: float = Field(default="Неизвестно")
    country_population: int = Field(default="Неизвестно")
    org: str = Field(default="Неизвестно")


class WeatherData(BaseModel):
    description: str
    icon: str
    main_temp: float
    main_pressure: int
    main_humidity: int
    visibility: int
    wind_speed: float
    sys_sunrise: int
    sys_sunset: int
    name: str


class GeoWeatherResponse(BaseModel):
    location: GeolocationData
    weather: WeatherData
    timestamp: int
