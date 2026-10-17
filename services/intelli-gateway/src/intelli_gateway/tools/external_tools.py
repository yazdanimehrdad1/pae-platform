"""Tools that call external HTTP APIs (with timeouts and retries in the client)."""

from pydantic import Field

from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.forecast import HourlyForecast
from intelli_gateway.schemas.tools import JSONValue, ToolInput
from intelli_gateway.services.forecast.client import ForecastClient
from intelli_gateway.tools.base import ToolDefinition, ToolError, tool
from intelli_gateway.utils.exceptions import ExternalApiError


class WeatherForecastInput(ToolInput):
    hours: int = Field(default=24, ge=1, le=72, description="Forecast horizon in hours (1-72).")


def summarize_forecast(forecast: HourlyForecast, hours: int) -> dict[str, JSONValue]:
    series = forecast.hourly

    def at(values: list[float | None], index: int) -> float | None:
        return values[index] if index < len(values) else None

    rows: list[JSONValue] = [
        {
            "time": time,
            "temperature_2m": at(series.temperature_2m, index),
            "cloud_cover": at(series.cloud_cover, index),
            "wind_speed_10m": at(series.wind_speed_10m, index),
            "shortwave_radiation": at(series.shortwave_radiation, index),
        }
        for index, time in enumerate(series.time[:hours])
    ]
    return {"hours": len(rows), "hourly": rows}


def build_external_tools(
    site_data: SiteDataConnector, forecast_client: ForecastClient
) -> list[ToolDefinition]:
    @tool(
        name="get_weather_forecast",
        description="""
Get the hourly weather forecast at this site's location: air temperature (degC), cloud cover
(%), wind speed at 10 m (km/h) and shortwave radiation (W/m2). Use it to explain or anticipate
PV and wind output, or temperature-related derating.
""",
        input_model=WeatherForecastInput,
    )
    async def get_weather_forecast(args: WeatherForecastInput, ctx: RequestContext) -> JSONValue:
        if ctx.site_id is None:
            raise ToolError("no site in request context")
        site = await site_data.get_site(ctx.site_id)
        if site is None or site.latitude is None or site.longitude is None:
            raise ToolError("this site has no coordinates")
        try:
            forecast = await forecast_client.hourly_forecast(
                site.latitude, site.longitude, args.hours
            )
        except ExternalApiError as error:
            raise ToolError(
                str(error), hint="the forecast service may be down; try later"
            ) from error
        return summarize_forecast(forecast, args.hours)

    return [get_weather_forecast]
