"""The PV forecast endpoints, end to end over fakes (no real provider, no network).

Invariant guarded: the three routes (series, refresh, health) only serialize what
ForecastService returns: AC power per site and PV device plus the weather, with ISO timestamps,
units, provider and interval convention; site access is enforced (403), refresh needs the admin
role; nothing stored is 404; a missing or reversed window is 422; the removed routes are gone.
"""

import httpx
from fakes import ScriptedLLMClient, make_settings
from forecast_fakes import SITE, fixed_now

from intelli_gateway.app import create_app
from intelli_gateway.fake_data.forecast import (
    FakePvPowerSource,
    FakeSiteConfigSource,
    FakeWeatherProvider,
)
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.schemas.api_models.forecast import (
    ForecastHealthResponse,
    PvForecastResponse,
    RefreshResponse,
)
from intelli_gateway.schemas.solar_forecast import INTERVAL_CONVENTION, UNITS
from intelli_gateway.solar_forecast.pv_model import PvlibPvModel
from intelli_gateway.solar_forecast.weather_model_source import WeatherModelSource
from intelli_gateway.wiring import build_services

ADMIN = {"X-Roles": "admin"}
BASE = f"/api/v1/sites/{SITE.site_id}/forecast"


def make_client(sources: list[PvForecastSource] | None = None) -> httpx.AsyncClient:
    settings = make_settings(ANTHROPIC_API_KEY="test-key")
    services = build_services(
        settings,
        llm=ScriptedLLMClient(),
        clock=fixed_now,
        site_configs=FakeSiteConfigSource((SITE,)),
        forecast_sources=sources
        or [WeatherModelSource(FakeWeatherProvider(clock=fixed_now), PvlibPvModel())],
    )
    app = create_app(settings, services)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def refreshed(client: httpx.AsyncClient) -> RefreshResponse:
    response = await client.post("/api/v1/forecast/refresh", headers=ADMIN)
    assert response.status_code == 200, response.text
    return RefreshResponse.model_validate(response.json())


class TestRefreshEndpoint:
    async def test_admin_refreshes(self) -> None:
        async with make_client() as client:
            result = await refreshed(client)
        (site,) = result.sites
        assert site.ok and site.provider == "fake_weather" and site.intervals > 0

    async def test_needs_admin(self) -> None:
        async with make_client() as client:
            response = await client.post("/api/v1/forecast/refresh")
        assert response.status_code == 403

    async def test_one_site_needs_access_to_it(self) -> None:
        async with make_client() as client:
            response = await client.post(
                "/api/v1/forecast/refresh",
                params={"site_id": SITE.site_id},
                headers={**ADMIN, "X-Site-Ids": "1"},
            )
        assert response.status_code == 403

    async def test_unknown_site_is_404(self) -> None:
        async with make_client() as client:
            response = await client.post(
                "/api/v1/forecast/refresh", params={"site_id": 9}, headers=ADMIN
            )
        assert response.status_code == 404


class TestSeriesEndpoint:
    PARAMS = {"start": "2026-06-15T10:00:00Z", "end": "2026-06-16T10:00:00Z"}

    async def test_nothing_stored_is_404(self) -> None:
        async with make_client() as client:
            response = await client.get(f"{BASE}/series", params=self.PARAMS)
        assert response.status_code == 404

    async def test_ac_power_and_weather_with_units_provider_and_convention(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            response = await client.get(f"{BASE}/series", params=self.PARAMS)
        assert response.status_code == 200
        raw_interval = response.json()["intervals"][0]
        assert set(raw_interval) == {
            "interval_start",
            "interval_end",
            "pv_ac_kw",
            "ghi",
            "temp_air_c",
            "wind_speed_ms",
            "cloud_cover_pct",
            "arrays",
        }
        assert set(raw_interval["arrays"][0]) == {"array_id", "pv_ac_kw"}
        body = PvForecastResponse.model_validate(response.json())
        assert body.provider == "fake_weather" and body.source_kind == "weather_model"
        assert body.units == UNITS and body.interval_convention == INTERVAL_CONVENTION
        assert body.resolution_minutes == 15
        # fixed_now is 10:07: the 10:00 interval began before the forecast was issued.
        assert body.intervals[0].interval_start.isoformat().startswith("2026-06-15T10:15")
        assert body.intervals[0].arrays[0].array_id == SITE.arrays[0].array_id

    async def test_window_is_required_and_ordered(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            missing_end = await client.get(f"{BASE}/series", params={"start": self.PARAMS["start"]})
            reversed_window = await client.get(
                f"{BASE}/series", params={"start": self.PARAMS["end"], "end": self.PARAMS["start"]}
            )
        assert missing_end.status_code == 422
        assert reversed_window.status_code == 422

    async def test_site_access_is_enforced(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            response = await client.get(
                f"{BASE}/series", params=self.PARAMS, headers={"X-Site-Ids": "1"}
            )
        assert response.status_code == 403

    async def test_pv_power_source_has_no_weather(self) -> None:
        async with make_client([FakePvPowerSource(clock=fixed_now)]) as client:
            await refreshed(client)
            response = await client.get(f"{BASE}/series", params=self.PARAMS)
        body = PvForecastResponse.model_validate(response.json())
        assert body.source_kind == "pv_power"
        assert all(interval.ghi is None and interval.arrays == [] for interval in body.intervals)

    async def test_removed_routes_are_gone(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            for path in ("", "/latest", "/summary?date=2026-06-15", "/raw", "/history"):
                assert (await client.get(f"{BASE}{path}")).status_code == 404, path


class TestHealthEndpoint:
    async def test_health_lists_only_accessible_sites(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            every = ForecastHealthResponse.model_validate(
                (await client.get("/api/v1/forecast/health")).json()
            )
            none = ForecastHealthResponse.model_validate(
                (await client.get("/api/v1/forecast/health", headers={"X-Site-Ids": "1"})).json()
            )
        assert every.active_provider == "fake_weather" and every.fallback_providers == []
        (site,) = every.sites
        assert site.site_id == SITE.site_id and site.last_provider == "fake_weather"
        assert not site.stale
        assert none.sites == []
