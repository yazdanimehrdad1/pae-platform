"""Wiring of the PV forecast: the source registry, the agent tool, the backend-ot site configs and
the migration splitter.

Invariant guarded: FORECAST_SOURCE / FORECAST_FALLBACK_SOURCES pick registered sources in order
(unknown names refused); get_pv_forecast reads the stored forecast for the context's site and
turns a missing forecast into an error result; backend-ot sites become SiteConfigs only with
coordinates and at least one PV array; migrations split on `;` outside quoted strings.
"""

from typing import cast

import httpx
import pytest
from fakes import make_ctx, make_settings
from forecast_fakes import SITE, fixed_now

from intelli_gateway.fake_data.forecast import (
    FakePvPowerSource,
    FakeSiteConfigSource,
    InMemoryForecastRepository,
)
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_config import BackendOtSiteConfigSource
from intelli_gateway.services.postgres.database import MIGRATIONS_DIR, split_statements
from intelli_gateway.solar_forecast.registry import build_sources
from intelli_gateway.solar_forecast.service import ForecastService, ForecastSettings
from intelli_gateway.tools.forecast_tools import build_forecast_tools
from intelli_gateway.tools.local_provider import LocalToolProvider
from intelli_gateway.utils.exceptions import ConfigurationError


class TestRegistry:
    def test_primary_then_fallbacks(self) -> None:
        settings = make_settings(
            FORECAST_SOURCE="open_meteo", FORECAST_FALLBACK_SOURCES="noaa_hrrr, fake, open_meteo"
        )
        assert [source.name for source in build_sources(settings, fixed_now)] == [
            "open_meteo",
            "noaa_hrrr",
            "fake",
        ]

    def test_unknown_source_is_refused(self) -> None:
        with pytest.raises(ConfigurationError, match="solcast"):
            build_sources(make_settings(FORECAST_SOURCE="solcast"), fixed_now)

    def test_open_meteo_reads_its_own_settings(self) -> None:
        settings = make_settings(
            OPEN_METEO_BASE_URL="http://open-meteo.internal:8080", OPEN_METEO_API_KEY="k"
        )
        (source,) = build_sources(settings, fixed_now)
        assert source.capabilities().commercial_use_allowed


async def service_with_forecast(stored: bool) -> ForecastService:
    service = ForecastService(
        sites=FakeSiteConfigSource((SITE,)),
        sources=[FakePvPowerSource(clock=fixed_now)],
        repository=InMemoryForecastRepository(),
        settings=ForecastSettings(True, 48, 15, 15, 90),
        clock=fixed_now,
    )
    if stored:
        await service.refresh()
    return service


class TestPvForecastTool:
    async def test_hourly_rows_for_the_context_site(self) -> None:
        tools = build_forecast_tools(await service_with_forecast(stored=True), fixed_now)
        provider = LocalToolProvider(tools, max_output_chars=20_000)
        result = await provider.call_tool(
            "get_pv_forecast", {"hours": 6}, make_ctx(site_id=SITE.site_id)
        )
        assert not result.is_error
        content = cast(dict[str, object], result.content)
        assert content["source"] == "fake_pv_power"
        rows = cast(list[dict[str, object]], content["hourly"])
        assert len(rows) == 6
        assert rows[0]["pv_ac_kw"] == 2500.0  # 10:00 UTC, inside the fake's 08-16 window

    async def test_no_forecast_is_an_error_result_with_a_hint(self) -> None:
        tools = build_forecast_tools(await service_with_forecast(stored=False), fixed_now)
        provider = LocalToolProvider(tools, max_output_chars=20_000)
        result = await provider.call_tool("get_pv_forecast", {}, make_ctx(site_id=SITE.site_id))
        assert result.is_error
        assert "hint" in cast(dict[str, object], result.content)


SITE_JSON = {
    "site_id": 1001,
    "client_id": "c",
    "name": "Powerflow 2BESS 1PV",
    "operator": "o",
    "capacity": "5 MWac PV",
    "device_count": 9,
    "created_at": "2026-06-01T00:00:00Z",
    "updated_at": "2026-06-01T00:00:00Z",
    "last_update": "2026-06-01T00:00:00Z",
    "coordinates": {"lat": 33.45, "lng": -112.07, "elevation_m": 331.0},
    "timezone": "America/Phoenix",
}
ARRAY_JSON = {
    "device_id": 7,
    "site_id": 1001,
    "device_name": "pv1",
    "device_type": "PV",
    "tilt_deg": 25.0,
    "azimuth_deg": 180.0,
    "dc_capacity_kw": 6500.0,
    "ac_capacity_kw": 5000.0,
    "system_loss_pct": 14.0,
    "temp_coefficient_pct_per_c": -0.35,
    "created_at": "2026-06-01T00:00:00Z",
    "updated_at": "2026-06-01T00:00:00Z",
}


def backend_ot(sites: list[dict[str, object]], arrays: dict[int, list[dict[str, object]]]):
    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/sites":
            return httpx.Response(200, json=sites)
        for site in sites:
            site_id = cast(int, site["site_id"])
            if path == f"/api/sites/{site_id}":
                return httpx.Response(200, json=site)
            if path == f"/api/sites/{site_id}/pv-arrays":
                return httpx.Response(200, json=arrays.get(site_id, []))
        return httpx.Response(404, json={"detail": "not found"})

    client = BackendOtClient(
        "http://backend-ot.test", timeout_s=1.0, attempts=1, transport=httpx.MockTransport(handle)
    )
    return BackendOtSiteConfigSource(client)


class TestBackendOtSiteConfigs:
    async def test_site_with_coordinates_and_arrays(self) -> None:
        source = backend_ot([SITE_JSON], {1001: [ARRAY_JSON]})
        (site,) = await source.list_sites()
        assert site.site_id == 1001 and site.timezone == "America/Phoenix"
        assert site.location.elevation_m == 331.0
        (array,) = site.arrays
        assert (array.array_id, array.name, array.dc_capacity_kw) == (7, "pv1", 6500.0)

    async def test_sites_without_coordinates_or_arrays_are_skipped(self) -> None:
        no_coordinates = {**SITE_JSON, "site_id": 1002, "coordinates": None}
        no_arrays = {**SITE_JSON, "site_id": 1003}
        source = backend_ot(
            [SITE_JSON, no_coordinates, no_arrays], {1001: [ARRAY_JSON], 1002: [ARRAY_JSON]}
        )
        assert [site.site_id for site in await source.list_sites()] == [1001]
        assert await source.get_site(1002) is None
        assert await source.get_site(1003) is None
        assert await source.get_site(4040) is None


class TestMigrations:
    def test_split_keeps_semicolons_inside_strings(self) -> None:
        sql = "-- header\nCREATE TABLE a (x TEXT);\nCOMMENT ON TABLE a IS 'one; two''s';\n"
        assert split_statements(sql) == [
            "CREATE TABLE a (x TEXT)",
            "COMMENT ON TABLE a IS 'one; two''s'",
        ]

    def test_migrations_are_numbered_and_split(self) -> None:
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        assert files and files[0].name == "001_forecasts.sql"
        for path in files:
            assert path.stem[:3].isdigit()
            assert split_statements(path.read_text(encoding="utf-8"))
