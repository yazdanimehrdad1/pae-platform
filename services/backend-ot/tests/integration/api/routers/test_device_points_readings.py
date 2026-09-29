"""
Integration tests for /api/device-point-readings.

Guards the read side of stored readings against a real database: latest-per-point,
timeseries ordering (newest first) and limits, time-window filtering, enum translation,
virtual points computed on read from their inputs' stored readings (never stored themselves),
display-timezone rendering, and the query validation rules (both at the endpoint and in
the global validate_time_range middleware).
"""

from datetime import UTC, datetime, timedelta

import asyncpg
from httpx import AsyncClient

from integration.factories import (
    create_device,
    create_site,
    create_virtual_point,
    insert_reading,
    point_request,
    upsert_points,
)
from schemas.api_models import (
    DevicePointResponse,
    LatestResponse,
    TimeseriesResponse,
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
    VirtualPointCreateRequest,
)

BASE_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
ENUM_DETAIL = {"0": "OFF", "1": "ON"}


async def arrange_readings(
    client: AsyncClient, db: asyncpg.Connection
) -> tuple[int, int, DevicePointResponse, DevicePointResponse]:
    """A device with a float point (3 readings, 1 min apart) and an enum point (1 reading)."""
    site = await create_site(client)
    device = await create_device(client, site.site_id)
    power, state = await upsert_points(
        client,
        site.site_id,
        device.device_id,
        [
            point_request(name="active_power", address=100, point_class="ANALOG"),
            point_request(
                name="state", address=110, size=1, data_type="enum16", enum_detail=ENUM_DETAIL
            ),
        ],
    )
    for minute, value in enumerate([10.0, 20.0, 30.0]):
        await insert_reading(db, power, BASE_TIME + timedelta(minutes=minute), value, value)
    await insert_reading(db, state, BASE_TIME, 1.0, 1.0)
    return site.site_id, device.device_id, power, state


def latest_url(site_id: int, device_id: int) -> str:
    return f"/api/device-point-readings/site/{site_id}/device/{device_id}/latest"


def timeseries_url(site_id: int, device_id: int) -> str:
    return f"/api/device-point-readings/timeseries/site/{site_id}/device/{device_id}"


async def get_latest(client: AsyncClient, url: str, **params: str | bool) -> LatestResponse:
    response = await client.get(url, params=params)
    assert response.status_code == 200, response.text
    return LatestResponse.model_validate(response.json())


async def get_timeseries(client: AsyncClient, url: str, **params: str | int) -> TimeseriesResponse:
    response = await client.get(url, params=params)
    assert response.status_code == 200, response.text
    return TimeseriesResponse.model_validate(response.json())


class TestLatest:
    async def test_returns_newest_reading_per_point(self, client, db):
        site_id, device_id, power, state = await arrange_readings(client, db)
        latest = await get_latest(client, latest_url(site_id, device_id))
        assert latest.meta.total_count == 2
        assert latest.readings[str(power.id)].value == 30.0
        assert latest.readings[str(state.id)].value == 1.0

    async def test_point_ids_filter(self, client, db):
        site_id, device_id, power, _ = await arrange_readings(client, db)
        latest = await get_latest(client, latest_url(site_id, device_id), point_ids=str(power.id))
        assert list(latest.readings) == [str(power.id)]

    async def test_translate_labels_enum_values(self, client, db):
        site_id, device_id, _, state = await arrange_readings(client, db)
        latest = await get_latest(client, latest_url(site_id, device_id), translate=True)
        assert latest.readings[str(state.id)].translated_value == "ON"

    async def test_device_without_readings_is_empty(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        latest = await get_latest(client, latest_url(site.site_id, device.device_id))
        assert latest.readings == {}


class TestTimeseries:
    async def test_newest_first_with_counts(self, client, db):
        site_id, device_id, power, _ = await arrange_readings(client, db)
        timeseries = await get_timeseries(client, timeseries_url(site_id, device_id))
        series = timeseries.readings[str(power.id)]
        assert series.count == 3
        assert [entry.value for entry in series.timeseries] == [30.0, 20.0, 10.0]

    async def test_limit_keeps_the_most_recent(self, client, db):
        site_id, device_id, power, _ = await arrange_readings(client, db)
        timeseries = await get_timeseries(client, timeseries_url(site_id, device_id), limit=2)
        series = timeseries.readings[str(power.id)]
        assert [entry.value for entry in series.timeseries] == [30.0, 20.0]

    async def test_time_window_filters_readings(self, client, db):
        site_id, device_id, power, _ = await arrange_readings(client, db)
        timeseries = await get_timeseries(
            client,
            timeseries_url(site_id, device_id),
            point_ids=str(power.id),
            start_time=(BASE_TIME + timedelta(seconds=30)).isoformat(),
            end_time=(BASE_TIME + timedelta(minutes=5)).isoformat(),
        )
        series = timeseries.readings[str(power.id)]
        assert [entry.value for entry in series.timeseries] == [30.0, 20.0]

    async def test_tz_renders_timestamps_in_that_zone(self, client, db):
        site_id, device_id, power, _ = await arrange_readings(client, db)
        timeseries = await get_timeseries(
            client,
            timeseries_url(site_id, device_id),
            point_ids=str(power.id),
            tz="America/Los_Angeles",
        )
        newest = timeseries.readings[str(power.id)].timeseries[0].time
        # Same instant (12:02 UTC), rendered in Pacific standard time (04:02 -08:00).
        assert newest == BASE_TIME + timedelta(minutes=2)
        assert newest.utcoffset() == timedelta(hours=-8)
        assert (newest.hour, newest.minute) == (4, 2)


class TestQueryValidation:
    async def test_time_range_with_explicit_bounds_is_422(self, client, db):
        site_id, device_id, _, _ = await arrange_readings(client, db)
        response = await client.get(
            timeseries_url(site_id, device_id),
            params={"time_range": "1H", "start_time": BASE_TIME.isoformat()},
        )
        assert response.status_code == 422

    async def test_naive_bound_without_tz_is_rejected(self, client, db):
        site_id, device_id, _, _ = await arrange_readings(client, db)
        response = await client.get(
            timeseries_url(site_id, device_id), params={"start_time": "2026-01-15T12:00:00"}
        )
        assert response.status_code == 422

    async def test_middleware_rejects_start_after_end(self, client, db):
        site_id, device_id, _, _ = await arrange_readings(client, db)
        response = await client.get(
            timeseries_url(site_id, device_id),
            params={
                "start_time": (BASE_TIME + timedelta(hours=1)).isoformat(),
                "end_time": BASE_TIME.isoformat(),
            },
        )
        assert response.status_code == 400

    async def test_middleware_rejects_unparseable_time(self, client, db):
        site_id, device_id, _, _ = await arrange_readings(client, db)
        response = await client.get(
            timeseries_url(site_id, device_id),
            params={"start_time": "yesterday", "end_time": BASE_TIME.isoformat()},
        )
        assert response.status_code == 400


class TestClassAndSeverity:
    async def test_latest_and_timeseries_carry_the_points_class(self, client, db):
        site_id, device_id, power, state = await arrange_readings(client, db)

        latest_response = await client.get(latest_url(site_id, device_id))
        raw_latest = latest_response.json()["readings"][str(power.id)]
        assert raw_latest["class"] == "ANALOG"  # wire name, not point_class
        latest = LatestResponse.model_validate(latest_response.json())
        assert latest.readings[str(power.id)].point_class == "ANALOG"
        assert latest.readings[str(state.id)].point_class is None

        timeseries = await get_timeseries(client, timeseries_url(site_id, device_id))
        assert timeseries.readings[str(power.id)].point_class == "ANALOG"


# --- Virtual points: computed on read from their inputs' stored readings ------------------


class VirtualArrangement:
    """Two devices polled 0.3 s apart every 10 s. On device A: SITE_POWER = power_a + power_b,
    and HIGH = 1 "high" while power_b >= 20, else 0 "low". Nothing is stored for either."""

    def __init__(self, site_id: int, device_id: int, power_a: DevicePointResponse,
                 power_b: DevicePointResponse, site_power: DevicePointResponse, high: DevicePointResponse):
        self.site_id, self.device_id = site_id, device_id
        self.power_a, self.power_b, self.site_power, self.high = power_a, power_b, site_power, high


async def arrange_virtual(client: AsyncClient, db: asyncpg.Connection) -> VirtualArrangement:
    site = await create_site(client)
    device_a = await create_device(client, site.site_id, name="meter-a")
    device_b = await create_device(client, site.site_id, name="meter-b", host="10.0.0.11")
    (power_a,) = await upsert_points(client, site.site_id, device_a.device_id, [point_request(name="power_a")])
    (power_b,) = await upsert_points(client, site.site_id, device_b.device_id, [point_request(name="power_b")])
    for cycle, (value_a, value_b) in enumerate([(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)]):
        cycle_start = BASE_TIME + timedelta(seconds=10 * cycle)
        await insert_reading(db, power_a, cycle_start, value_a, value_a)
        await insert_reading(db, power_b, cycle_start + timedelta(seconds=0.3), value_b, value_b)

    site_power = await create_virtual_point(client, site.site_id, device_a.device_id, VirtualPointCreateRequest(
        name="SITE_POWER", unit="kW",
        definition=VirtualCalculationDefinition(kind="calculation", function="sum", inputs=[power_a.id, power_b.id]),
    ))
    high = await create_virtual_point(client, site.site_id, device_a.device_id, VirtualPointCreateRequest(
        name="HIGH",
        definition=VirtualConditionDefinition(
            kind="condition",
            cases=[VirtualCase(output=1, label="high", when=VirtualConditionGroup(match="all", items=[
                VirtualCondition(point_id=power_b.id, operator=">=", value=20),
            ]))],
            default_output=0,
            default_label="low",
        ),
    ))
    return VirtualArrangement(site.site_id, device_a.device_id, power_a, power_b, site_power, high)


def series_of(response: TimeseriesResponse, point: DevicePointResponse) -> list[tuple[float, float | None]]:
    return [
        ((sample.time - BASE_TIME).total_seconds(), sample.value)
        for sample in response.readings[str(point.id)].timeseries
    ]


class TestVirtualTimeseries:
    async def test_computed_from_inputs_on_other_devices_newest_first(self, client, db):
        arranged = await arrange_virtual(client, db)
        response = await get_timeseries(
            client, timeseries_url(arranged.site_id, arranged.device_id), point_ids=str(arranged.site_power.id)
        )
        # One sample per poll cycle, at the later device's time.
        assert series_of(response, arranged.site_power) == [(20.3, 33.0), (10.3, 22.0), (0.3, 11.0)]
        assert response.readings[str(arranged.site_power.id)].count == 3
        assert response.readings[str(arranged.site_power.id)].unit == "kW"

    async def test_limit_and_window_apply_to_computed_values(self, client, db):
        arranged = await arrange_virtual(client, db)
        url = timeseries_url(arranged.site_id, arranged.device_id)
        point_id = str(arranged.site_power.id)

        limited = await get_timeseries(client, url, point_ids=point_id, limit=2)
        assert series_of(limited, arranged.site_power) == [(20.3, 33.0), (10.3, 22.0)]

        # The window starts after power_a's reading at 10 s: its value is carried in from before.
        windowed = await get_timeseries(
            client, url, point_ids=point_id,
            start_time=(BASE_TIME + timedelta(seconds=10.2)).isoformat(),
            end_time=(BASE_TIME + timedelta(seconds=15)).isoformat(),
        )
        assert series_of(windowed, arranged.site_power) == [(10.3, 22.0)]

    async def test_mixed_with_stored_points_and_all_points_of_the_device(self, client, db):
        arranged = await arrange_virtual(client, db)
        url = timeseries_url(arranged.site_id, arranged.device_id)
        mixed = await get_timeseries(client, url, point_ids=f"{arranged.power_a.id},{arranged.site_power.id}")
        assert series_of(mixed, arranged.power_a) == [(20.0, 3.0), (10.0, 2.0), (0.0, 1.0)]
        assert series_of(mixed, arranged.site_power)[0] == (20.3, 33.0)

        everything = await get_timeseries(client, url)
        assert set(everything.readings) == {str(arranged.power_a.id), str(arranged.site_power.id), str(arranged.high.id)}

    async def test_rows_stored_under_a_virtual_point_are_ignored(self, client, db):
        arranged = await arrange_virtual(client, db)
        await insert_reading(db, arranged.site_power, BASE_TIME + timedelta(seconds=5), 999.0, 999.0)
        response = await get_timeseries(
            client, timeseries_url(arranged.site_id, arranged.device_id), point_ids=str(arranged.site_power.id)
        )
        assert 999.0 not in [value for _, value in series_of(response, arranged.site_power)]

    async def test_condition_values_translate_to_their_state_names(self, client, db):
        arranged = await arrange_virtual(client, db)
        response = await get_timeseries(
            client, timeseries_url(arranged.site_id, arranged.device_id), point_ids=str(arranged.high.id), translate="true"
        )
        readings = response.readings[str(arranged.high.id)]
        assert [sample.translated_value for sample in readings.timeseries] == ["high", "high", "low"]


class TestVirtualLatest:
    async def test_latest_is_computed_from_the_newest_inputs(self, client, db):
        arranged = await arrange_virtual(client, db)
        latest = await get_latest(
            client, latest_url(arranged.site_id, arranged.device_id),
            point_ids=f"{arranged.site_power.id},{arranged.high.id}", translate="true",
        )
        site_power = latest.readings[str(arranged.site_power.id)]
        assert (site_power.value, site_power.time) == (33.0, BASE_TIME + timedelta(seconds=20.3))
        assert latest.readings[str(arranged.high.id)].translated_value == "high"

    async def test_latest_is_empty_when_an_input_is_stale(self, client, db):
        arranged = await arrange_virtual(client, db)
        # power_a moves an hour ahead; power_b's newest reading is far older than the max gap.
        await insert_reading(db, arranged.power_a, BASE_TIME + timedelta(hours=1), 4.0, 4.0)
        latest = await get_latest(
            client, latest_url(arranged.site_id, arranged.device_id), point_ids=str(arranged.site_power.id)
        )
        reading = latest.readings[str(arranged.site_power.id)]
        assert (reading.value, reading.time) == (None, None)
