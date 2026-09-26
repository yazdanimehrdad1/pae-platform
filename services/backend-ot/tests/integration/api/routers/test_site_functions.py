"""
Integration tests for /api/site-functions.

Guards the site-specific function routing against a real database: discovery lists what
the site's profile offers with each function's kind, each sample function (common-,
site-, device-) computes from stored readings inside the requested window, and requests
resolve to 404 when the site, device, profile, function or point doesn't exist.
"""

from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import AsyncClient

from integration.factories import (
    create_device,
    create_site,
    insert_reading,
    point_request,
    upsert_points,
)
from schemas.api_models import DevicePointCreateRequest, DevicePointResponse
from schemas.site_profiles import (
    EnergySummaryResult,
    SiteEndpointsResponse,
)
from schemas.site_profiles.individual_sites.alpha_solar import (
    InverterAvailabilityResult,
    PoiPowerResult,
)
from schemas.tests_models import ApiErrorDetail, ApiErrorResponse

BASE_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
WINDOW = {
    "start_time": BASE_TIME.isoformat(),
    "end_time": (BASE_TIME + timedelta(hours=2)).isoformat(),
}
INVERTER_STATES = {"3": "mppt", "4": "derating", "5": "fault", "6": "night"}
PLANT_MODES = {"1": "derate", "2": "running", "3": "standby", "5": "fault"}


def enum_point(name: str, address: int, enum_detail: dict[str, str]) -> DevicePointCreateRequest:
    return point_request(name=name, address=address, size=1, data_type="enum16", enum_detail=enum_detail)


async def insert_series(
    db: asyncpg.Connection, point: DevicePointResponse, values: list[float], step: timedelta
) -> None:
    for index, value in enumerate(values):
        await insert_reading(db, point, BASE_TIME + step * index, value, value)


def url(site_id: int, function: str, device_id: int | None = None) -> str:
    if device_id is None:
        return f"/api/site-functions/site/{site_id}/{function}"
    return f"/api/site-functions/site/{site_id}/device/{device_id}/{function}"


async def assert_not_found(client: AsyncClient, path: str) -> ApiErrorDetail:
    response = await client.get(path, params=WINDOW)
    assert response.status_code == 404, response.text
    error = ApiErrorResponse.model_validate(response.json())
    assert isinstance(error.detail, ApiErrorDetail)
    assert error.detail.error == "NotFoundError"
    return error.detail


class TestDiscovery:
    async def test_lists_declared_endpoints_with_kind_and_method(self, client):
        site = await create_site(client, profile="alpha_solar")
        response = await client.get(f"/api/site-functions/site/{site.site_id}")
        assert response.status_code == 200
        listing = SiteEndpointsResponse.model_validate(response.json())
        assert listing.profile == "alpha_solar"
        assert {(endpoint.name, endpoint.kind, endpoint.method) for endpoint in listing.endpoints} == {
            ("common-energy-summary", "common", "GET"),
            ("site-poi-power", "site", "GET"),
            ("device-inverter-availability", "device", "GET"),
            ("device-plant-inverter-availability", "device", "GET"),
        }

    async def test_default_site_lists_only_common_endpoints(self, client):
        site = await create_site(client)
        response = await client.get(f"/api/site-functions/site/{site.site_id}")
        assert response.status_code == 200
        listing = SiteEndpointsResponse.model_validate(response.json())
        assert listing.profile == "default"
        assert [(endpoint.name, endpoint.kind) for endpoint in listing.endpoints] == [
            ("common-energy-summary", "common")
        ]

    async def test_unknown_site_is_404(self, client):
        response = await client.get("/api/site-functions/site/9999")
        assert response.status_code == 404


class TestCommonEnergySummary:
    async def test_integrates_each_devices_power_point(self, client, db):
        site = await create_site(client, profile="alpha_solar")
        inverter = await create_device(client, site.site_id, name="device_1")
        plant = await create_device(client, site.site_id, name="device_3")
        (watts,) = await upsert_points(
            client, site.site_id, inverter.device_id, [point_request(name="active_power", unit="W")]
        )
        (kilowatts,) = await upsert_points(
            client, site.site_id, plant.device_id, [point_request(name="active_power", unit="kW")]
        )
        # 1000 W for 1 h = 1 kWh; 2 kW for 1 h = 2 kWh
        await insert_series(db, watts, [1000.0, 1000.0, 1000.0], timedelta(minutes=30))
        await insert_series(db, kilowatts, [2.0, 2.0], timedelta(hours=1))

        response = await client.get(url(site.site_id, "common-energy-summary"), params=WINDOW)
        assert response.status_code == 200, response.text
        result = EnergySummaryResult.model_validate(response.json())
        by_device = {device.device_name: device for device in result.devices}
        assert by_device["device_1"].energy_kwh == pytest.approx(1.0)
        assert by_device["device_1"].sample_count == 3
        assert by_device["device_3"].energy_kwh == pytest.approx(2.0)
        assert result.energy_kwh == pytest.approx(3.0)

    async def test_ignores_readings_outside_the_window(self, client, db):
        site = await create_site(client, profile="alpha_solar")
        device = await create_device(client, site.site_id, name="device_1")
        (watts,) = await upsert_points(
            client, site.site_id, device.device_id, [point_request(name="active_power", unit="W")]
        )
        await insert_series(db, watts, [1000.0, 1000.0, 1000.0], timedelta(hours=1))
        params = {**WINDOW, "end_time": (BASE_TIME + timedelta(hours=1)).isoformat()}
        response = await client.get(url(site.site_id, "common-energy-summary"), params=params)
        result = EnergySummaryResult.model_validate(response.json())
        assert result.devices[0].sample_count == 2
        assert result.energy_kwh == pytest.approx(1.0)

    async def test_devices_without_the_power_point_are_left_out(self, client):
        site = await create_site(client, profile="alpha_solar")
        await create_device(client, site.site_id, name="device_2")
        response = await client.get(url(site.site_id, "common-energy-summary"), params=WINDOW)
        result = EnergySummaryResult.model_validate(response.json())
        assert result.devices == []
        assert result.energy_kwh == pytest.approx(0.0)

    async def test_default_site_serves_it(self, client, db):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="device_1")
        (watts,) = await upsert_points(
            client, site.site_id, device.device_id, [point_request(name="active_power", unit="W")]
        )
        await insert_series(db, watts, [1000.0, 1000.0, 1000.0], timedelta(minutes=30))
        response = await client.get(url(site.site_id, "common-energy-summary"), params=WINDOW)
        assert response.status_code == 200, response.text
        assert EnergySummaryResult.model_validate(response.json()).energy_kwh == pytest.approx(1.0)

    async def test_unknown_site_is_404(self, client):
        await assert_not_found(client, url(9999, "common-energy-summary"))

    async def test_conflicting_window_params_are_422(self, client):
        site = await create_site(client, profile="alpha_solar")
        params = {**WINDOW, "time_range": "1D"}
        response = await client.get(url(site.site_id, "common-energy-summary"), params=params)
        assert response.status_code == 422

    async def test_missing_window_is_422(self, client):
        site = await create_site(client, profile="alpha_solar")
        response = await client.get(url(site.site_id, "common-energy-summary"))
        assert response.status_code == 422


class TestSitePoiPower:
    async def test_returns_series_oldest_first_with_peak_and_average(self, client, db):
        site = await create_site(client, profile="alpha_solar")
        plant = await create_device(client, site.site_id, name="device_3")
        (poi,) = await upsert_points(
            client,
            site.site_id,
            plant.device_id,
            [point_request(name="poi_active_power_total", unit="kW")],
        )
        await insert_series(db, poi, [100.0, 300.0, 200.0], timedelta(minutes=10))

        response = await client.get(url(site.site_id, "site-poi-power"), params=WINDOW)
        assert response.status_code == 200, response.text
        result = PoiPowerResult.model_validate(response.json())
        assert [sample.value for sample in result.series.timeseries] == [100.0, 300.0, 200.0]
        assert result.series.count == 3
        assert result.peak_kw == 300.0
        assert result.average_kw == 200.0

    async def test_site_without_poi_point_is_404(self, client):
        site = await create_site(client, profile="alpha_solar")
        detail = await assert_not_found(client, url(site.site_id, "site-poi-power"))
        assert "poi_active_power_total" in detail.message


class TestDeviceInverterAvailability:
    async def test_default_reads_inverter_state(self, client, db):
        site = await create_site(client, profile="alpha_solar")
        inverter = await create_device(client, site.site_id, name="device_1")
        (state,) = await upsert_points(
            client, site.site_id, inverter.device_id, [enum_point("inverter_state", 1, INVERTER_STATES)]
        )
        # mppt, derating, fault, night -> 2 of 4 online
        await insert_series(db, state, [3.0, 4.0, 5.0, 6.0], timedelta(minutes=10))

        response = await client.get(url(site.site_id, "device-inverter-availability", inverter.device_id), params=WINDOW)
        assert response.status_code == 200, response.text
        result = InverterAvailabilityResult.model_validate(response.json())
        assert result.state_points == ["inverter_state"]
        assert result.sample_count == 4
        assert result.online_sample_count == 2
        assert result.availability_pct == 50.0

    async def test_plant_version_pools_the_four_inverter_modes(self, client, db):
        site = await create_site(client, profile="alpha_solar")
        plant = await create_device(client, site.site_id, name="device_3")
        modes = await upsert_points(
            client,
            site.site_id,
            plant.device_id,
            [enum_point(f"inv0{n}_mode", n, PLANT_MODES) for n in range(1, 5)],
        )
        # derate/running count as online: 3 of 4 inverters online
        for mode, value in zip(modes, [1.0, 2.0, 2.0, 5.0], strict=True):
            await insert_reading(db, mode, BASE_TIME, value, value)

        response = await client.get(
            url(site.site_id, "device-plant-inverter-availability", plant.device_id), params=WINDOW
        )
        assert response.status_code == 200, response.text
        result = InverterAvailabilityResult.model_validate(response.json())
        assert result.state_points == ["inv01_mode", "inv02_mode", "inv03_mode", "inv04_mode"]
        assert result.online_states == [1, 2]
        assert result.sample_count == 4
        assert result.availability_pct == 75.0

    async def test_no_readings_gives_null_availability(self, client):
        site = await create_site(client, profile="alpha_solar")
        inverter = await create_device(client, site.site_id, name="device_1")
        await upsert_points(
            client, site.site_id, inverter.device_id, [enum_point("inverter_state", 1, INVERTER_STATES)]
        )
        response = await client.get(url(site.site_id, "device-inverter-availability", inverter.device_id), params=WINDOW)
        result = InverterAvailabilityResult.model_validate(response.json())
        assert result.sample_count == 0
        assert result.availability_pct is None

    async def test_device_without_state_point_is_404(self, client):
        site = await create_site(client, profile="alpha_solar")
        device = await create_device(client, site.site_id, name="device_2")
        detail = await assert_not_found(client, url(site.site_id, "device-inverter-availability", device.device_id))
        assert "inverter_state" in detail.message

    async def test_device_from_another_site_is_404(self, client):
        site = await create_site(client, profile="alpha_solar", name="Alpha")
        other = await create_site(client, profile="alpha_solar", name="Other")
        foreign = await create_device(client, other.site_id, name="device_1")
        await assert_not_found(client, url(site.site_id, "device-inverter-availability", foreign.device_id))

    async def test_default_version_on_plant_device_is_404(self, client):
        # device-inverter-availability on device_3 looks for inverter_state, which it doesn't have
        site = await create_site(client, profile="alpha_solar")
        plant = await create_device(client, site.site_id, name="device_3")
        detail = await assert_not_found(
            client, url(site.site_id, "device-inverter-availability", plant.device_id)
        )
        assert "inverter_state" in detail.message

    async def test_default_site_has_no_site_or_device_endpoints(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="device_1")
        await assert_not_found(client, url(site.site_id, "site-poi-power"))
        detail = await assert_not_found(
            client, url(site.site_id, "device-inverter-availability", device.device_id)
        )
        assert "profile 'default'" in detail.message

    async def test_function_name_without_prefix_is_404(self, client):
        site = await create_site(client, profile="alpha_solar")
        response = await client.get(f"/api/site-functions/site/{site.site_id}/energy-summary", params=WINDOW)
        assert response.status_code == 404

    async def test_unknown_device_is_404(self, client):
        site = await create_site(client, profile="alpha_solar")
        await assert_not_found(client, url(site.site_id, "device-inverter-availability", 9999))
