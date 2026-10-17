"""Example external HTTP API client: an Open-Meteo-compatible forecast endpoint.

Every call has a timeout and is retried (tenacity) on connection errors, timeouts and 5xx.
4xx responses are not retried.
"""

import httpx
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from intelli_gateway.schemas.forecast import HourlyForecast
from intelli_gateway.utils.exceptions import ExternalApiError


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, httpx.TransportError):  # connect/read errors and timeouts
        return True
    return isinstance(error, httpx.HTTPStatusError) and error.response.status_code >= 500


class ForecastClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
        max_wait_s: float = 4.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout_s), transport=transport
        )
        self._attempts = attempts
        self._max_wait_s = max_wait_s

    async def hourly_forecast(
        self, latitude: float, longitude: float, hours: int
    ) -> HourlyForecast:
        params: dict[str, str | int | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,cloud_cover,wind_speed_10m,shortwave_radiation",
            "forecast_hours": hours,
            "timezone": "UTC",
        }
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._attempts),
                wait=wait_exponential(multiplier=0.5, max=self._max_wait_s),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.get("", params=params)
                    response.raise_for_status()
                    return HourlyForecast.model_validate_json(response.content)
        except ValidationError as error:
            raise ExternalApiError("forecast service returned an unexpected payload") from error
        except httpx.HTTPError as error:
            raise ExternalApiError(f"forecast request failed: {type(error).__name__}") from error
        raise ExternalApiError("forecast request failed")  # unreachable: reraise=True

    async def aclose(self) -> None:
        await self._client.aclose()
