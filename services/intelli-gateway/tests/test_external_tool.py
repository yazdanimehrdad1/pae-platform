"""The external API tool: timeouts and retries in the client, errors returned as results."""

import json
from typing import cast

import httpx
from fakes import fixed_clock, make_ctx

from intelli_gateway.fake_data.site_data import FakeSiteDataConnector
from intelli_gateway.services.forecast.client import ForecastClient
from intelli_gateway.tools.external_tools import build_external_tools
from intelli_gateway.tools.local_provider import LocalToolProvider

FORECAST = {
    "hourly": {
        "time": ["2026-06-15T12:00", "2026-06-15T13:00", "2026-06-15T14:00"],
        "temperature_2m": [24.1, 25.0, 25.3],
        "cloud_cover": [10, 20, 35],
        "wind_speed_10m": [8.0, 9.5, 11.0],
        "shortwave_radiation": [820, 790, 700],
    }
}


def make_provider(handler: httpx.MockTransport) -> LocalToolProvider:
    client = ForecastClient(
        base_url="https://forecast.test/v1/forecast",
        timeout_s=1.0,
        attempts=3,
        transport=handler,
        max_wait_s=0.0,
    )
    tools = build_external_tools(FakeSiteDataConnector(clock=fixed_clock), client)
    return LocalToolProvider(tools, max_output_chars=10_000)


class TestGetWeatherForecast:
    async def test_sends_site_coordinates_and_returns_hourly_rows(self) -> None:
        seen: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=FORECAST)

        result = await make_provider(httpx.MockTransport(handle)).call_tool(
            "get_weather_forecast", {"hours": 2}, make_ctx(site_id=1)
        )
        assert not result.is_error
        content = cast(dict[str, object], result.content)
        assert content["hours"] == 2
        assert seen[0].url.params["latitude"] == "48.1"
        assert seen[0].url.params["forecast_hours"] == "2"

    async def test_retries_server_errors(self) -> None:
        calls: list[int] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json=FORECAST)

        result = await make_provider(httpx.MockTransport(handle)).call_tool(
            "get_weather_forecast", {}, make_ctx(site_id=1)
        )
        assert not result.is_error
        assert len(calls) == 3

    async def test_gives_up_after_the_last_attempt(self) -> None:
        calls: list[int] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            raise httpx.ConnectTimeout("slow", request=request)

        result = await make_provider(httpx.MockTransport(handle)).call_tool(
            "get_weather_forecast", {}, make_ctx(site_id=1)
        )
        assert result.is_error
        assert len(calls) == 3
        assert "hint" in cast(dict[str, object], result.content)

    async def test_client_errors_are_not_retried(self) -> None:
        calls: list[int] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(400)

        result = await make_provider(httpx.MockTransport(handle)).call_tool(
            "get_weather_forecast", {}, make_ctx(site_id=1)
        )
        assert result.is_error
        assert len(calls) == 1

    async def test_unexpected_payload_is_an_error_result(self) -> None:
        def handle(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=json.dumps({"daily": {}}))

        result = await make_provider(httpx.MockTransport(handle)).call_tool(
            "get_weather_forecast", {}, make_ctx(site_id=1)
        )
        assert result.is_error
