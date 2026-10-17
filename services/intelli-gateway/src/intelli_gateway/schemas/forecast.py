"""The forecast API's response, as far as the forecast tool reads it."""

from pydantic import BaseModel


class HourlySeries(BaseModel):
    time: list[str]
    temperature_2m: list[float | None] = []
    cloud_cover: list[float | None] = []
    wind_speed_10m: list[float | None] = []
    shortwave_radiation: list[float | None] = []


class HourlyForecast(BaseModel):
    hourly: HourlySeries
