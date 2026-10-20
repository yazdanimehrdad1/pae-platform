"""The PV forecast tool: reads the stored forecast through ForecastService (no upstream call)."""

from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import Field

from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.solar_forecast import UNITS
from intelli_gateway.schemas.tools import JSONValue, ToolInput
from intelli_gateway.solar_forecast.service import ForecastService
from intelli_gateway.tools.base import ToolDefinition, ToolError, tool
from intelli_gateway.utils.exceptions import NotFoundError


class PvForecastInput(ToolInput):
    hours: int = Field(default=24, ge=1, le=48, description="Hours ahead from now (1-48).")


def _round(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


def build_forecast_tools(
    forecast: ForecastService, clock: Callable[[], datetime]
) -> list[ToolDefinition]:
    @tool(
        name="get_pv_forecast",
        description="""
Get this site's PV production forecast, hour by hour from now: AC power (kW) and energy (kWh),
with the weather behind it when the source provides it (global horizontal irradiance W/m2, air
temperature degC, wind m/s, cloud cover %). Use it to anticipate PV output, explain expected
derating or clipping, or compare a live reading with what was forecast.
""",
        input_model=PvForecastInput,
    )
    async def get_pv_forecast(args: PvForecastInput, ctx: RequestContext) -> JSONValue:
        if ctx.site_id is None:
            raise ToolError("no site in request context")
        # Whole hours, starting with the one running now.
        start = clock().replace(minute=0, second=0, microsecond=0)
        try:
            result = await forecast.get_forecast(
                ctx.site_id, start, start + timedelta(hours=args.hours), resolution_minutes=60
            )
        except NotFoundError as error:
            raise ToolError(
                str(error),
                hint="the site may have no coordinates or PV arrays configured, or the first "
                "refresh hasn't run yet",
            ) from error
        rows: list[JSONValue] = [
            {
                "start": interval.interval_start.isoformat(),
                "pv_ac_kw": _round(interval.pv_ac_kw),
                "pv_energy_kwh": _round(interval.pv_energy_kwh),
                "ghi": _round(interval.ghi),
                "temp_air_c": _round(interval.temp_air_c),
                "wind_speed_ms": _round(interval.wind_speed_ms),
                "cloud_cover_pct": _round(interval.cloud_cover_pct),
            }
            for interval in result.intervals
        ]
        units: dict[str, JSONValue] = dict(UNITS)
        return {
            "source": result.source_name,
            "issued_at": result.issued_at.isoformat(),
            "fallback_used": result.fallback_used,
            "units": units,
            "hourly": rows,
        }

    return [get_pv_forecast]
