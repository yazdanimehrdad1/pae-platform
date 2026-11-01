"""
Integration tests for the Powerflow 2BESS 1PV site's functions (/api/site-functions).

Invariant guarded: against a real database, a site with the powerflow_2bess_1pv profile offers
site-poi-active-power, site-poi-reactive-power, site-assets-active-power and
site-assets-reactive-power; each is its SPF points summed at each poll timestamp (devices read
milliseconds apart in one poll count as one timestamp), with peak and average, export positive.
The assets are BESS 1 + BESS 2 + PV 1: the load and the POI meter are on the site but not summed.
site-bess1/2-round-trip-efficiency read that BESS's power and SoC through their SPF points and give
its SoC-corrected round trip efficiency; site-bess1/2-rolling-round-trip-efficiency give it at every
whole step of the window (15 min for a 2 h window), each over the last lookback_days (read from
before the window).
A missing device or an unlinked STANDARDIZED point is a 404 naming it; a missing window is a 422.
"""

from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import AsyncClient

from integration.factories import (
    create_device,
    create_site,
    insert_reading,
    link_point,
    point_request,
    standardized_points_by_name,
    upsert_points,
)
from schemas.api_models import DevicePointResponse, SiteResponse, StandardizedPointLinkRequest
from schemas.site_profiles import SiteEndpointsResponse
from schemas.site_profiles.individual_sites.powerflow_2bess_1pv import (
    BessRollingRoundTripEfficiencyResult,
    BessRoundTripEfficiencyResult,
    PowerSeriesResult,
)
from schemas.tests_models import ApiErrorResponse

PROFILE = "powerflow_2bess_1pv"
BASE_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
POLL = timedelta(seconds=20)
WINDOW = {"start_time": BASE_TIME.isoformat(), "end_time": (BASE_TIME + timedelta(hours=1)).isoformat()}

# Two live polls of the simulated site (kW / kvar): (device, type, reactive point name, linked
# STANDARDIZED points, active power per poll, reactive power per poll, ms after the poll it's read).
DEVICES = (
    ("2bess_1pv-bess1", "BESS", "Var", ("BESS_ACTIVE_POWER",), (-1129.0, -1721.0), (10.0, -20.0), 560),
    ("2bess_1pv-bess2", "BESS", "Var", ("BESS_ACTIVE_POWER",), (-1412.0, -1639.0), (5.0, 5.0), 556),
    ("2bess_1pv-pv1", "PV", "Var", ("PV_ACTIVE_POWER",), (2122.0, 2117.0), (-30.0, 40.0), 551),
    ("2bess_1pv-load1", "IED", "VAR", ("IED_ACTIVE_POWER",), (2924.0, 2919.0), (500.0, 500.0), 549),
    (
        "2bess_1pv-poi_meter", "METER", "VAR", ("METER_ACTIVE_POWER", "METER_REACTIVE_POWER"),
        (-3399.0, -4227.0), (100.0, 200.0), 558,
    ),
)


def url(site_id: int, function: str) -> str:
    return f"/api/site-functions/site/{site_id}/{function}"


async def add_device(
    client: AsyncClient, site_id: int, name: str, device_type: str, reactive_name: str, linked: tuple[str, ...]
) -> tuple[DevicePointResponse, DevicePointResponse]:
    """A device with NATIVE active (W) and reactive power points in kW / kvar, and its STANDARDIZED
    points `linked` linked to them (active power points to W, reactive ones to the reactive point)."""
    device = await create_device(client, site_id, name=name, type=device_type)
    active, reactive = await upsert_points(
        client,
        site_id,
        device.device_id,
        [point_request(name="W", address=100, unit="kW"), point_request(name=reactive_name, address=102, unit="kvar")],
    )
    standardized = await standardized_points_by_name(client, site_id, device.device_id)
    for name_of_point in linked:
        source, unit = (reactive, "kvar") if "REACTIVE" in name_of_point else (active, "kW")
        await link_point(client, standardized[name_of_point], StandardizedPointLinkRequest(source_point_id=source.id, unit=unit))
    return active, reactive


async def seeded_site(client: AsyncClient, db: asyncpg.Connection) -> SiteResponse:
    """The site with every device of DEVICES and their two polls of readings."""
    site = await create_site(client, profile=PROFILE)
    for name, device_type, reactive_name, linked, active_values, reactive_values, read_after_ms in DEVICES:
        active, reactive = await add_device(client, site.site_id, name, device_type, reactive_name, linked)
        for poll, (active_value, reactive_value) in enumerate(zip(active_values, reactive_values, strict=True)):
            time = BASE_TIME + POLL * poll + timedelta(milliseconds=read_after_ms)
            await insert_reading(db, active, time, active_value, active_value)
            await insert_reading(db, reactive, time, reactive_value, reactive_value)
    return site


async def get_series(client: AsyncClient, site_id: int, function: str) -> PowerSeriesResult:
    response = await client.get(url(site_id, function), params=WINDOW)
    assert response.status_code == 200, response.text
    return PowerSeriesResult.model_validate(response.json())


async def not_found_message(client: AsyncClient, site_id: int, function: str) -> str:
    response = await client.get(url(site_id, function), params=WINDOW)
    assert response.status_code == 404, response.text
    return ApiErrorResponse.model_validate(response.json()).detail.message


def values(result: PowerSeriesResult) -> list[tuple[datetime, float | None]]:
    return [(sample.time, sample.value) for sample in result.series.timeseries]


POLL_TIMES = [BASE_TIME + timedelta(seconds=1), BASE_TIME + POLL + timedelta(seconds=1)]  # rounded to the second

# The worked example at 100x, truly 90.25 % (both ways 95 %), hourly: 8000 kWh charged with the
# ramps, then 6270 kWh discharged while 1000 kWh stays stored (SoC 50 -> 60 % of 10 MWh).
RTE_POWER_KW = (0.0, -4000.0, -4000.0, 0.0, 3135.0, 3135.0, 0.0)
RTE_SOC_PCT = (50.0, 50.0, 50.0, 60.0, 60.0, 60.0, 60.0)
RTE_WINDOW = {"start_time": BASE_TIME.isoformat(), "end_time": (BASE_TIME + timedelta(hours=7)).isoformat()}


async def add_bess(client: AsyncClient, site_id: int, name: str, link_soc: bool = True) -> tuple[DevicePointResponse, DevicePointResponse]:
    """A BESS with NATIVE power (kW) and SoC (%) points, BESS_ACTIVE_POWER and (link_soc)
    BESS_STATE_OF_CHARGE linked to them."""
    device = await create_device(client, site_id, name=name, type="BESS")
    power, soc = await upsert_points(
        client,
        site_id,
        device.device_id,
        [point_request(name="W", address=100, unit="kW"), point_request(name="SoC", address=102, unit="%")],
    )
    standardized = await standardized_points_by_name(client, site_id, device.device_id)
    await link_point(client, standardized["BESS_ACTIVE_POWER"], StandardizedPointLinkRequest(source_point_id=power.id, unit="kW"))
    if link_soc:
        await link_point(client, standardized["BESS_STATE_OF_CHARGE"], StandardizedPointLinkRequest(source_point_id=soc.id, unit="%"))
    return power, soc


class TestPowerflow2Bess1PvFunctions:
    async def test_the_profile_offers_its_functions(self, client):
        site = await create_site(client, profile=PROFILE)
        response = await client.get(f"/api/site-functions/site/{site.site_id}")
        assert response.status_code == 200, response.text
        listing = SiteEndpointsResponse.model_validate(response.json())
        assert {(endpoint.name, endpoint.output) for endpoint in listing.endpoints} == {
            ("site-poi-active-power", "series"),
            ("site-poi-reactive-power", "series"),
            ("site-assets-active-power", "series"),
            ("site-assets-reactive-power", "series"),
            ("site-bess1-round-trip-efficiency", "scalar"),
            ("site-bess2-round-trip-efficiency", "scalar"),
            ("site-bess1-rolling-round-trip-efficiency", "series"),
            ("site-bess2-rolling-round-trip-efficiency", "series"),
        }

    async def test_assets_active_power_is_bess1_plus_bess2_plus_pv1_at_each_poll(self, client, db):
        site = await seeded_site(client, db)
        result = await get_series(client, site.site_id, "site-assets-active-power")
        # -1129 - 1412 + 2122 and -1721 - 1639 + 2117; the load and the POI meter aren't summed
        assert values(result) == list(zip(POLL_TIMES, [-419.0, -1243.0], strict=True))
        assert (result.unit, result.peak, result.average) == ("kW", -419.0, -831.0)
        assert (result.series.id, result.series.unit) == (0, "kW")

    async def test_assets_reactive_power_is_bess1_plus_bess2_plus_pv1_at_each_poll(self, client, db):
        site = await seeded_site(client, db)
        result = await get_series(client, site.site_id, "site-assets-reactive-power")
        assert values(result) == list(zip(POLL_TIMES, [-15.0, 25.0], strict=True))
        assert (result.unit, result.peak, result.average) == ("kvar", 25.0, 5.0)

    async def test_poi_active_and_reactive_power_are_the_meters(self, client, db):
        site = await seeded_site(client, db)
        active = await get_series(client, site.site_id, "site-poi-active-power")
        reactive = await get_series(client, site.site_id, "site-poi-reactive-power")
        assert values(active) == list(zip(POLL_TIMES, [-3399.0, -4227.0], strict=True))
        assert values(reactive) == list(zip(POLL_TIMES, [100.0, 200.0], strict=True))
        assert (active.peak, active.average) == (-3399.0, -3813.0)

    async def test_no_readings_gives_an_empty_series_and_null_stats(self, client):
        site = await create_site(client, profile=PROFILE)
        await add_device(client, site.site_id, "2bess_1pv-poi_meter", "METER", "VAR", ("METER_ACTIVE_POWER",))
        result = await get_series(client, site.site_id, "site-poi-active-power")
        assert (result.series.timeseries, result.peak, result.average) == ([], None, None)

    async def test_a_missing_device_is_a_404_naming_it(self, client):
        site = await create_site(client, profile=PROFILE)
        for name, device_type, reactive_name, linked, *_ in DEVICES[:2]:
            await add_device(client, site.site_id, name, device_type, reactive_name, linked)
        assert "2bess_1pv-pv1" in await not_found_message(client, site.site_id, "site-assets-active-power")

    async def test_an_unlinked_standardized_point_is_a_404_naming_it(self, client):
        site = await create_site(client, profile=PROFILE)
        await add_device(client, site.site_id, "2bess_1pv-poi_meter", "METER", "VAR", ())
        message = await not_found_message(client, site.site_id, "site-poi-reactive-power")
        assert "METER_REACTIVE_POWER isn't linked" in message

    async def test_bess_round_trip_efficiency_is_soc_corrected(self, client, db):
        site = await create_site(client, profile=PROFILE)
        power, soc = await add_bess(client, site.site_id, "2bess_1pv-bess2")
        for hour, (power_kw, soc_pct) in enumerate(zip(RTE_POWER_KW, RTE_SOC_PCT, strict=True)):
            time = BASE_TIME + timedelta(hours=hour)
            await insert_reading(db, power, time, power_kw, power_kw)
            await insert_reading(db, soc, time, soc_pct, soc_pct)

        response = await client.get(url(site.site_id, "site-bess2-round-trip-efficiency"), params=RTE_WINDOW)

        assert response.status_code == 200, response.text
        result = BessRoundTripEfficiencyResult.model_validate(response.json())
        round_trip = result.round_trip
        assert (result.bess, round_trip.boundary, round_trip.status, round_trip.method) == (
            "2bess_1pv-bess2", "ac", "ok", "soc_corrected",
        )
        assert (round_trip.charged_kwh, round_trip.discharged_kwh) == (pytest.approx(8000.0), pytest.approx(6270.0))
        assert (round_trip.soc_start_pct, round_trip.soc_end_pct) == (50.0, 60.0)
        assert round_trip.stored_energy_change_kwh == pytest.approx(1000.0)
        assert round_trip.round_trip_efficiency_pct == pytest.approx(90.25)

    async def test_rolling_round_trip_efficiency_looks_back_before_the_window(self, client, db):
        site = await create_site(client, profile=PROFILE)
        power, soc = await add_bess(client, site.site_id, "2bess_1pv-bess1")
        for hour, (power_kw, soc_pct) in enumerate(zip(RTE_POWER_KW, RTE_SOC_PCT, strict=True)):
            time = BASE_TIME + timedelta(hours=hour)
            await insert_reading(db, power, time, power_kw, power_kw)
            await insert_reading(db, soc, time, soc_pct, soc_pct)

        # the window starts as the cycle ends: every value's 1-day lookback holds the whole cycle
        window = {
            "start_time": (BASE_TIME + timedelta(hours=6)).isoformat(),
            "end_time": (BASE_TIME + timedelta(hours=8)).isoformat(),
            "lookback_days": 1,
        }
        response = await client.get(url(site.site_id, "site-bess1-rolling-round-trip-efficiency"), params=window)

        assert response.status_code == 200, response.text
        result = BessRollingRoundTripEfficiencyResult.model_validate(response.json())
        assert (result.bess, result.lookback_days, result.step_minutes) == ("2bess_1pv-bess1", 1, 15)
        assert result.values_by_status == {"ok": 9}
        assert [sample.time for sample in result.series.timeseries] == [
            BASE_TIME + timedelta(hours=6, minutes=15 * index) for index in range(9)
        ]
        assert [sample.value for sample in result.series.timeseries] == [pytest.approx(90.25)] * 9
        assert (result.series.id, result.series.unit) == (0, "%")

    async def test_rolling_round_trip_efficiency_keeps_hours_without_a_value(self, client):
        site = await create_site(client, profile=PROFILE)
        await add_bess(client, site.site_id, "2bess_1pv-bess2")
        response = await client.get(
            url(site.site_id, "site-bess2-rolling-round-trip-efficiency"), params={**RTE_WINDOW, "lookback_days": 2}
        )

        assert response.status_code == 200, response.text
        result = BessRollingRoundTripEfficiencyResult.model_validate(response.json())
        # 7 h at 15 min: 29 values, none computable without readings
        assert result.values_by_status == {"missing_soc_data": 29}
        assert [sample.value for sample in result.series.timeseries] == [None] * 29

    @pytest.mark.parametrize("lookback_days", [0, 91])
    async def test_rolling_lookback_out_of_range_is_422(self, client, lookback_days):
        site = await create_site(client, profile=PROFILE)
        response = await client.get(
            url(site.site_id, "site-bess1-rolling-round-trip-efficiency"),
            params={**RTE_WINDOW, "lookback_days": lookback_days},
        )
        assert response.status_code == 422, response.text

    async def test_bess_round_trip_efficiency_needs_its_soc_linked(self, client):
        site = await create_site(client, profile=PROFILE)
        await add_bess(client, site.site_id, "2bess_1pv-bess1", link_soc=False)
        message = await not_found_message(client, site.site_id, "site-bess1-round-trip-efficiency")
        assert "BESS_STATE_OF_CHARGE isn't linked" in message

    async def test_missing_window_is_422(self, client):
        site = await create_site(client, profile=PROFILE)
        response = await client.get(url(site.site_id, "site-assets-active-power"))
        assert response.status_code == 422, response.text
