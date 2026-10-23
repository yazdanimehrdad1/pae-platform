"""Open-Meteo /v1/forecast response (https://open-meteo.com/en/docs). Only
services/open_meteo/provider.py uses these; nothing else may depend on Open-Meteo's format.

`minutely_15` / `hourly` hold index-aligned arrays keyed by variable name. Radiation values are
the mean over the PRECEDING step; temperature and wind are instantaneous at `time`.
"""

from pydantic import BaseModel, ConfigDict


class OpenMeteoSeries(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: list[str]
    shortwave_radiation: list[float | None] | None = None
    direct_normal_irradiance: list[float | None] | None = None
    diffuse_radiation: list[float | None] | None = None
    global_tilted_irradiance: list[float | None] | None = None
    temperature_2m: list[float | None] | None = None
    wind_speed_10m: list[float | None] | None = None
    cloud_cover: list[float | None] | None = None


class OpenMeteoForecastResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latitude: float
    longitude: float
    utc_offset_seconds: int = 0
    minutely_15: OpenMeteoSeries | None = None
    hourly: OpenMeteoSeries | None = None


class OpenMeteoErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    error: bool = True
    reason: str = "unknown error"
