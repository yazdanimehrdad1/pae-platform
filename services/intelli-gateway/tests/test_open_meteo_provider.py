"""OpenMeteoProvider's own conventions, beyond the shared provider contract.

Invariant guarded: requests ask for UTC, the 15-minute variables, the site's elevation and each
array plane (azimuth converted from clockwise-from-north to Open-Meteo's 0 = south), one request
per distinct plane; a radiation value stamped t becomes the interval [t - 15 min, t); wind km/h
becomes m/s; null tail values are dropped; 429/5xx/timeouts are retried, other 4xx are not; the
API key is sent only when configured; the free hosted API is flagged non-commercial.
"""

from datetime import timedelta

import httpx
import pytest
from forecast_fakes import (
    FORECAST_NOW,
    SITE,
    TWO_PLANE_SITE,
    open_meteo_payload,
    open_meteo_provider,
)
from pydantic import SecretStr

from intelli_gateway.services.open_meteo.provider import OpenMeteoProvider, to_open_meteo_azimuth
from intelli_gateway.utils.exceptions import ProviderError


class TestAzimuth:
    @pytest.mark.parametrize(
        ("ours", "theirs"), [(180, 0), (90, -90), (270, 90), (0, -180), (135, -45), (359, 179)]
    )
    def test_conversion(self, ours: float, theirs: float) -> None:
        assert to_open_meteo_azimuth(ours) == theirs


class TestRequests:
    async def test_parameters(self) -> None:
        seen: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=open_meteo_payload(request))

        provider = open_meteo_provider(handle)
        await provider.fetch_forecast(SITE, 48, 15)
        (request,) = seen
        params = request.url.params
        assert request.url.path == "/v1/forecast"
        assert params["timezone"] == "UTC"
        assert params["latitude"] == "33.45" and params["longitude"] == "-112.07"
        assert params["elevation"] == "331.0"
        assert params["tilt"] == "25.0" and params["azimuth"] == "0.0"
        assert set(params["minutely_15"].split(",")) == {
            "shortwave_radiation",
            "direct_normal_irradiance",
            "diffuse_radiation",
            "global_tilted_irradiance",
            "temperature_2m",
            "wind_speed_10m",
        }
        assert int(params["forecast_days"]) >= 3  # covers now + 48 h from today 00:00
        assert "apikey" not in params

    async def test_one_request_per_distinct_plane(self) -> None:
        seen: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=open_meteo_payload(request))

        site = TWO_PLANE_SITE.model_copy(
            update={
                "arrays": (
                    *TWO_PLANE_SITE.arrays,
                    TWO_PLANE_SITE.arrays[0].model_copy(update={"array_id": 9}),
                )
            }
        )
        weather = await open_meteo_provider(handle).fetch_forecast(site, 24, 15)
        planes = sorted((r.url.params["tilt"], r.url.params["azimuth"]) for r in seen)
        assert planes == [("10.0", "-90.0"), ("25.0", "0.0")]
        gti_only = [r for r in seen if r.url.params["minutely_15"] == "global_tilted_irradiance"]
        assert len(gti_only) == 1
        noon = next(i for i in weather.intervals if i.interval_start.hour == 19)
        # Arrays 7 and 9 share a plane (same POA); array 8 has its own (flatter -> lower here).
        assert noon.poa_by_array[7] == noon.poa_by_array[9]
        assert noon.poa_by_array[8] < noon.poa_by_array[7]

    async def test_api_key_is_sent_when_configured(self) -> None:
        seen: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=open_meteo_payload(request))

        provider = OpenMeteoProvider(
            base_url="https://customer-api.open-meteo.com",
            timeout_s=1.0,
            attempts=1,
            api_key=SecretStr("secret-key"),
            transport=httpx.MockTransport(handle),
            clock=lambda: FORECAST_NOW,
        )
        await provider.fetch_forecast(SITE, 24, 15)
        assert seen[0].url.params["apikey"] == "secret-key"
        assert seen[0].url.host == "customer-api.open-meteo.com"
        assert provider.capabilities().commercial_use_allowed


class TestNormalization:
    async def test_interval_is_the_preceding_step_and_units_are_si(self) -> None:
        weather = await open_meteo_provider().fetch_forecast(SITE, 48, 15)
        first = weather.intervals[0]
        # FORECAST_NOW is 10:07: the first interval still running is [10:00, 10:15).
        assert first.interval_start == FORECAST_NOW.replace(minute=0)
        assert first.interval_end == FORECAST_NOW.replace(minute=15)
        assert first.wind_speed_ms == pytest.approx(2.0)  # 7.2 km/h
        assert weather.issued_at == FORECAST_NOW

    async def test_horizon_is_trimmed_and_null_tail_dropped(self) -> None:
        weather = await open_meteo_provider().fetch_forecast(SITE, 6, 15)
        assert weather.intervals[-1].interval_start < FORECAST_NOW + timedelta(hours=6)
        assert len(weather.intervals) == 6 * 4 + 1  # the running interval plus 6 h

        long = await open_meteo_provider().fetch_forecast(SITE, 384, 15)
        assert all(interval.ghi is not None for interval in long.intervals)

    async def test_15_minute_intervals_take_cloud_cover_from_their_hour(self) -> None:
        seen: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=open_meteo_payload(request))

        weather = await open_meteo_provider(handle).fetch_forecast(TWO_PLANE_SITE, 6, 15)
        base = [r for r in seen if "shortwave_radiation" in r.url.params["minutely_15"]]
        assert [r.url.params.get("hourly") for r in base] == ["cloud_cover"]
        assert len(seen) == 2  # still one request per plane: cloud cover rides on the base one
        by_start = {interval.interval_start: interval for interval in weather.intervals}
        for minute in (15, 30, 45):
            assert by_start[FORECAST_NOW.replace(minute=minute)].cloud_cover_pct == 20.0  # 10:xx
        assert by_start[FORECAST_NOW.replace(hour=11, minute=0)].cloud_cover_pct == 22.0

    async def test_hourly_series_carries_cloud_cover(self) -> None:
        weather = await open_meteo_provider().fetch_forecast(SITE, 24, 60)
        assert weather.intervals[0].interval_end - weather.intervals[0].interval_start == (
            timedelta(hours=1)
        )
        assert weather.intervals[0].cloud_cover_pct == 10.0

    async def test_horizon_out_of_range_is_refused(self) -> None:
        with pytest.raises(ProviderError):
            await open_meteo_provider().fetch_forecast(SITE, 385, 15)


class TestRetries:
    @pytest.mark.parametrize("status", [429, 500, 503])
    async def test_transient_errors_are_retried(self, status: int) -> None:
        calls: list[int] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 3:
                return httpx.Response(status)
            return httpx.Response(200, json=open_meteo_payload(request))

        await open_meteo_provider(handle).fetch_forecast(SITE, 24, 15)
        assert len(calls) == 3

    async def test_gives_up_after_the_last_attempt(self) -> None:
        calls: list[int] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            raise httpx.ConnectTimeout("slow", request=request)

        with pytest.raises(ProviderError, match="unreachable"):
            await open_meteo_provider(handle).fetch_forecast(SITE, 24, 15)
        assert len(calls) == 3

    async def test_client_errors_are_not_retried_and_carry_the_reason(self) -> None:
        calls: list[int] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(400, json={"error": True, "reason": "Latitude out of range"})

        with pytest.raises(ProviderError, match="Latitude out of range"):
            await open_meteo_provider(handle).fetch_forecast(SITE, 24, 15)
        assert len(calls) == 1


class TestCapabilitiesAndHealth:
    def test_free_hosted_api_is_non_commercial(self) -> None:
        assert not open_meteo_provider().capabilities().commercial_use_allowed
        self_hosted = open_meteo_provider(base_url="http://open-meteo.internal:8080")
        assert self_hosted.capabilities().commercial_use_allowed

    async def test_health_check(self) -> None:
        assert await open_meteo_provider().health_check()
        down = open_meteo_provider(lambda request: httpx.Response(503), attempts=1)
        assert not await down.health_check()
