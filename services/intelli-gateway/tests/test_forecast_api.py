"""The PV forecast endpoints, end to end over fakes (no real provider, no network).

Invariant guarded: routes only serialize what ForecastService returns, with ISO timestamps,
units, provider and interval convention; site access is enforced (403), refresh needs the admin
role; nothing stored is 404; a bad resolution is 422; ?format=csv returns CSV.
"""

import csv
import io
from datetime import UTC, datetime

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
    DailySummaryResponse,
    ForecastHealthResponse,
    PvForecastResponse,
    RefreshResponse,
    WeatherForecastResponse,
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


class TestReadEndpoints:
    async def test_nothing_stored_is_404(self) -> None:
        async with make_client() as client:
            response = await client.get(f"{BASE}/latest")
        assert response.status_code == 404

    async def test_latest_carries_units_provider_and_convention(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            response = await client.get(f"{BASE}/latest")
        assert response.status_code == 200
        body = PvForecastResponse.model_validate(response.json())
        assert body.provider == "fake_weather" and body.source_kind == "weather_model"
        assert body.units == UNITS and body.interval_convention == INTERVAL_CONVENTION
        assert body.intervals[0].interval_start.tzinfo is not None
        assert (
            response.json()["intervals"][0]["interval_start"].endswith("Z")
            or "+00:00" in (response.json()["intervals"][0]["interval_start"])
        )
        assert body.intervals[0].arrays[0].array_id == SITE.arrays[0].array_id

    async def test_window_resolution_and_csv(self) -> None:
        start = datetime(2026, 6, 15, 18, 0, tzinfo=UTC)
        end = datetime(2026, 6, 15, 21, 0, tzinfo=UTC)
        params = {"start": start.isoformat(), "end": end.isoformat(), "resolution": 60}
        async with make_client() as client:
            await refreshed(client)
            response = await client.get(BASE, params=params)
            as_csv = await client.get(BASE, params={**params, "format": "csv"})
            bad = await client.get(BASE, params={"resolution": 20})
        body = PvForecastResponse.model_validate(response.json())
        assert body.resolution_minutes == 60
        assert [interval.interval_start for interval in body.intervals] == [
            datetime(2026, 6, 15, hour, 0, tzinfo=UTC) for hour in (18, 19, 20)
        ]
        assert as_csv.status_code == 200
        assert as_csv.headers["content-type"].startswith("text/csv")
        rows = list(csv.DictReader(io.StringIO(as_csv.text)))
        assert len(rows) == 3 and float(rows[1]["pv_ac_kw"]) == body.intervals[1].pv_ac_kw
        assert bad.status_code == 422

    async def test_summary_history_and_raw(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            summary = await client.get(f"{BASE}/summary", params={"date": "2026-06-15"})
            history = await client.get(
                f"{BASE}/history", params={"issued_before": "2026-06-16T00:00:00+00:00"}
            )
            too_early = await client.get(
                f"{BASE}/history", params={"issued_before": "2026-06-01T00:00:00+00:00"}
            )
            raw = await client.get(f"{BASE}/raw")
        day = DailySummaryResponse.model_validate(summary.json())
        assert day.provider == "fake_weather" and day.energy_kwh > 0 and day.peak_kw > 0
        assert history.status_code == 200
        assert too_early.status_code == 404
        weather = WeatherForecastResponse.model_validate(raw.json())
        assert weather.provider == "fake_weather" and weather.units == UNITS

    async def test_raw_is_404_for_a_pv_power_source(self) -> None:
        async with make_client([FakePvPowerSource(clock=fixed_now)]) as client:
            await refreshed(client)
            response = await client.get(f"{BASE}/raw")
        assert response.status_code == 404
        assert "no weather" in response.json()["detail"]

    async def test_site_access_is_enforced(self) -> None:
        async with make_client() as client:
            await refreshed(client)
            for path in ("", "/latest", "/summary?date=2026-06-15", "/raw"):
                response = await client.get(f"{BASE}{path}", headers={"X-Site-Ids": "1"})
                assert response.status_code == 403, path


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
