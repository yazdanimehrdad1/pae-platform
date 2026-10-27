"""
Integration tests for profile virtual points (helpers.profile_points) against a real database, with
alpha_solar's declared poi_apparent_power (sqrt(P^2 + Q^2) on mock-device-3).

Guards the sync (the point's row appears when its device does, a re-run never duplicates it, a user
VIRTUAL point of that name is adopted) and the compute job (values are stored under the input
polls' timestamps and read back like a NATIVE point's, the watermark moves, a re-run is idempotent,
a poll inside the settle time waits, and a failing or slow function keeps its window for the next
run).
"""

import asyncio
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import AsyncClient

import helpers.profile_points.compute as compute_module
from config import settings
from helpers.profile_points.compute import compute_site_profile_points
from helpers.profile_points.sync import sync_site_profile_points
from integration.factories import (
    ALPHA_POI_DEVICE,
    create_alpha_poi_device,
    create_device,
    create_site,
    create_virtual_point,
    device_points,
    insert_reading,
    point_request,
    upsert_points,
)
from schemas.api_models import (
    DevicePointResponse,
    DeviceUpdate,
    DeviceWithPoints,
    TimeseriesResponse,
    VirtualCalculationDefinition,
    VirtualPointCreateRequest,
)
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import VirtualPointContext

POINT = "poi_apparent_power"
DECLARED = compute_module.SITE_PROFILES_BY_KEY["alpha_solar"].virtual_points[0]
NOW = datetime.now(UTC).replace(microsecond=0)
SETTLE = timedelta(seconds=settings.profile_point_settle_seconds)


async def set_computed_until(db: asyncpg.Connection, point: DevicePointResponse, until: datetime) -> None:
    await db.execute(
        "INSERT INTO profile_point_state (device_point_id, computed_until) VALUES ($1, $2)", point.id, until
    )


async def computed_until(db: asyncpg.Connection, point: DevicePointResponse) -> datetime | None:
    return await db.fetchval("SELECT computed_until FROM profile_point_state WHERE device_point_id = $1", point.id)


async def stored_count(db: asyncpg.Connection, point: DevicePointResponse) -> int:
    return await db.fetchval("SELECT count(*) FROM device_points_readings WHERE device_point_id = $1", point.id)


async def read_series(
    client: AsyncClient, point: DevicePointResponse, end: datetime = NOW
) -> list[tuple[datetime, float | None]]:
    response = await client.get(
        f"/api/device-point-readings/timeseries/site/{point.site_id}/device/{point.device_id}",
        params={
            "point_ids": str(point.id),
            "start_time": (NOW - timedelta(hours=1)).isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    series = TimeseriesResponse.model_validate(response.json()).readings[str(point.id)]
    return [(entry.time, entry.value) for entry in reversed(series.timeseries)]


async def arrange_polls(
    client: AsyncClient, db: asyncpg.Connection, polls: list[tuple[datetime, float, float]]
) -> DevicePointResponse:
    """The alpha POI device with P and Q readings at each poll; returns the profile point."""
    site, device, (active, reactive) = await create_alpha_poi_device(client)
    for time, active_value, reactive_value in polls:
        await insert_reading(db, active, time, active_value, active_value)
        await insert_reading(db, reactive, time, reactive_value, reactive_value)
    return (await device_points(client, site.site_id, device.device_id))[POINT]


class TestSync:
    async def test_creating_the_device_gives_it_the_profile_point(self, client):
        site, device, _ = await create_alpha_poi_device(client)
        point = (await device_points(client, site.site_id, device.device_id))[POINT]
        assert (point.category, point.profile_point_key, point.unit) == ("VIRTUAL", POINT, "kVA")
        assert (point.data_type, point.virtual_definition) == ("float32", None)
        assert point.profile_point_description == DECLARED.description

    async def test_resync_refreshes_the_description_from_code(self, client, db):
        site, device, _ = await create_alpha_poi_device(client)
        await db.execute(
            "UPDATE device_points SET profile_point_description = 'stale' WHERE profile_point_key IS NOT NULL"
        )

        await sync_site_profile_points(site.site_id)

        point = (await device_points(client, site.site_id, device.device_id))[POINT]
        assert point.profile_point_description == DECLARED.description

    async def test_description_needs_a_profile_key(self, client, db):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        (power,) = await upsert_points(client, site.site_id, device.device_id, [point_request()])
        with pytest.raises(asyncpg.CheckViolationError):
            await db.execute("UPDATE device_points SET profile_point_description = 'x' WHERE id = $1", power.id)

    async def test_resync_does_not_duplicate(self, client):
        site, device, _ = await create_alpha_poi_device(client)
        before = await device_points(client, site.site_id, device.device_id)
        plan = await sync_site_profile_points(site.site_id)
        assert plan.create == {}
        assert plan.refresh == {POINT: before[POINT].id}
        assert await device_points(client, site.site_id, device.device_id) == before

    async def test_device_of_another_name_or_site_without_profile_gets_none(self, client):
        site = await create_site(client, profile="alpha_solar")
        other = await create_device(client, site.site_id, name="rtac-1")
        assert POINT not in await device_points(client, site.site_id, other.device_id)
        plain = await create_site(client, name="Plain Site")
        plain_device = await create_device(client, plain.site_id, name=ALPHA_POI_DEVICE)
        assert POINT not in await device_points(client, plain.site_id, plain_device.device_id)

    async def test_user_virtual_point_of_that_name_is_adopted_when_its_device_takes_the_name(self, client):
        site = await create_site(client, profile="alpha_solar")
        device = await create_device(client, site.site_id, name="meter-before-rename")
        (power,) = await upsert_points(client, site.site_id, device.device_id, [point_request()])
        user_point = await create_virtual_point(client, site.site_id, device.device_id, VirtualPointCreateRequest(
            name=POINT,
            definition=VirtualCalculationDefinition(kind="calculation", function="sum", inputs=[power.id]),
        ))

        response = await client.put(
            f"/api/devices/site/{site.site_id}/devices/{device.device_id}",
            json=DeviceUpdate(name=ALPHA_POI_DEVICE).model_dump(mode="json", exclude_unset=True),
        )
        assert response.status_code == 200, response.text
        DeviceWithPoints.model_validate(response.json())

        adopted = (await device_points(client, site.site_id, device.device_id))[POINT]
        assert adopted.id == user_point.id
        assert (adopted.profile_point_key, adopted.virtual_definition, adopted.unit) == (POINT, None, "kVA")
        assert adopted.profile_point_description == DECLARED.description


class TestCompute:
    async def test_values_are_stored_at_the_input_polls_and_read_back(self, client, db):
        first, second = NOW - timedelta(seconds=60), NOW - timedelta(seconds=50)
        point = await arrange_polls(client, db, [(first, 3.0, 4.0), (second, 6.0, 8.0)])
        await set_computed_until(db, point, NOW - timedelta(minutes=5))

        await compute_site_profile_points(point.site_id, NOW)

        assert await read_series(client, point) == [(first, 5.0), (second, 10.0)]
        assert await computed_until(db, point) == NOW - SETTLE

    async def test_rerun_over_the_same_window_is_idempotent(self, client, db):
        point = await arrange_polls(client, db, [(NOW - timedelta(seconds=60), 3.0, 4.0)])
        await set_computed_until(db, point, NOW - timedelta(minutes=5))
        await compute_site_profile_points(point.site_id, NOW)
        await db.execute("UPDATE profile_point_state SET computed_until = $1", NOW - timedelta(minutes=5))

        await compute_site_profile_points(point.site_id, NOW)

        assert await stored_count(db, point) == 1

    async def test_poll_inside_the_settle_time_waits_for_the_next_run(self, client, db):
        recent = NOW - SETTLE / 2
        point = await arrange_polls(client, db, [(NOW - timedelta(seconds=60), 3.0, 4.0), (recent, 6.0, 8.0)])
        await set_computed_until(db, point, NOW - timedelta(minutes=5))

        await compute_site_profile_points(point.site_id, NOW)
        assert [time for time, _ in await read_series(client, point)] == [NOW - timedelta(seconds=60)]

        await compute_site_profile_points(point.site_id, NOW + SETTLE)
        assert [time for time, _ in await read_series(client, point)] == [NOW - timedelta(seconds=60), recent]

    async def test_first_run_without_backfill_starts_the_clock_and_the_next_run_computes(self, client, db):
        later_poll = NOW + timedelta(seconds=5)
        point = await arrange_polls(
            client, db, [(NOW - timedelta(minutes=2), 3.0, 4.0), (later_poll, 6.0, 8.0)]
        )

        await compute_site_profile_points(point.site_id, NOW)
        assert await stored_count(db, point) == 0
        assert await computed_until(db, point) == NOW - SETTLE

        await compute_site_profile_points(point.site_id, NOW + timedelta(seconds=20))
        assert await read_series(client, point, end=NOW + timedelta(minutes=1)) == [(later_poll, 10.0)]
        assert await computed_until(db, point) == NOW + timedelta(seconds=20) - SETTLE

    @pytest.mark.parametrize("failure", ["raises", "times_out"])
    async def test_failing_function_keeps_its_window(self, client, db, monkeypatch, failure):
        async def broken(ctx: VirtualPointContext) -> list[TimestampedValue]:
            if failure == "raises":
                raise RuntimeError("bad input")
            await asyncio.sleep(1)
            return []

        start = NOW - timedelta(minutes=5)
        point = await arrange_polls(client, db, [(NOW - timedelta(seconds=60), 3.0, 4.0)])
        await set_computed_until(db, point, start)
        profile = compute_module.SITE_PROFILES_BY_KEY["alpha_solar"]
        (declared,) = profile.virtual_points
        broken_profile = profile.model_copy(
            update={"virtual_points": (declared.model_copy(update={"compute": broken}),)}
        )
        monkeypatch.setitem(compute_module.SITE_PROFILES_BY_KEY, "alpha_solar", broken_profile)
        monkeypatch.setattr(settings, "profile_point_timeout_seconds", 0.05)

        await compute_site_profile_points(point.site_id, NOW)

        assert await stored_count(db, point) == 0
        assert await computed_until(db, point) == start
