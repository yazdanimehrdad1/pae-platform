"""
Integration tests for helpers.alarms.evaluation.evaluate_site_alarms (one evaluation cycle).

Guards, against stored readings and a controlled `now`:
- a threshold raises only after its delay, records the value and the point's device, holds
  inside the deadband and clears past it; point-vs-point thresholds use the other point's value;
- an input older than the max gap counts as missing (no raise);
- comms-stale raises back-dated to last success + timeout and clears on the next stored reading;
- a multi-point condition raises and clears; a disabled alarm is not raised.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from pydantic import TypeAdapter

from helpers.alarms.evaluation import evaluate_site_alarms
from helpers.virtual_points.resolve import input_max_gap
from integration.factories import (
    create_alarm,
    create_device,
    create_site,
    insert_reading,
    point_request,
    upsert_points,
)
from schemas.api_models import DevicePointResponse, VirtualCondition, VirtualConditionGroup
from schemas.api_models.alarms import (
    AlarmDefinitionCreateRequest,
    AlarmDefinitionUpdateRequest,
    AlarmEventResponse,
    CommsStaleAlarm,
    ConditionAlarm,
    ThresholdAlarm,
)

NOW = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
EVENT_LIST = TypeAdapter(list[AlarmEventResponse])


def at(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


async def site_with_points(client: AsyncClient) -> tuple[int, int, list[DevicePointResponse]]:
    """A site with one device and three points: power, other_power (floats) and flags (bitfield)."""
    site = await create_site(client)
    device = await create_device(client, site.site_id)
    points = await upsert_points(client, site.site_id, device.device_id, [
        point_request(name="power"),
        point_request(name="other_power", address=110),
        point_request(name="flags", address=120, size=1, data_type="bitfield16", bitfield_detail={"3": "trip"}),
    ])
    return site.site_id, device.device_id, points


def threshold_alarm(point_id: int, delay_sec: int = 0, deadband: float = 0, **condition: object) -> AlarmDefinitionCreateRequest:
    return AlarmDefinitionCreateRequest(
        name="power_high", severity="warning", message="Power too high",
        rule=ThresholdAlarm(kind="threshold", delay_sec=delay_sec, deadband=deadband,
                            condition=VirtualCondition.model_validate({"point_id": point_id, "operator": ">", "value": 10} | condition)),
    )


async def events(client: AsyncClient, site_id: int) -> list[AlarmEventResponse]:
    response = await client.get(f"/api/alarms/site/{site_id}/events", params={
        "start_time": (NOW - timedelta(days=1)).isoformat(), "end_time": (NOW + timedelta(days=1)).isoformat(),
    })
    assert response.status_code == 200, response.text
    return EVENT_LIST.validate_python(response.json())


async def reading(db, point: DevicePointResponse, seconds: int, value: float) -> None:
    await insert_reading(db, point, at(seconds), value, value)


class TestThreshold:
    async def test_delay_then_raise_hold_in_deadband_then_clear(self, client, db):
        site_id, device_id, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm(power.id, delay_sec=20, deadband=2))

        await reading(db, power, 0, 12)
        assert await evaluate_site_alarms(site_id, at(0)) == []
        await reading(db, power, 10, 13)
        assert await evaluate_site_alarms(site_id, at(10)) == []
        await reading(db, power, 20, 14)
        (raised,) = await evaluate_site_alarms(site_id, at(20))
        assert (raised.kind, raised.at) == ("raise", at(20))

        (event,) = await events(client, site_id)
        assert (event.definition_id, event.device_id, event.value_at_raise) == (alarm.id, device_id, 14)
        assert (event.raised_at, event.cleared_at, event.message, event.severity) == (at(20), None, "Power too high", "warning")

        await reading(db, power, 30, 9)  # below the limit, inside the deadband
        assert await evaluate_site_alarms(site_id, at(30)) == []
        await reading(db, power, 40, 7.5)
        (cleared,) = await evaluate_site_alarms(site_id, at(40))
        assert cleared.kind == "clear"
        (event,) = await events(client, site_id)
        assert event.cleared_at == at(40)

    async def test_an_edited_rule_closes_the_old_event_and_raises_after_its_own_delay(self, client, db):
        site_id, _, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm(power.id, delay_sec=20))
        await reading(db, power, 0, 50)
        await evaluate_site_alarms(site_id, at(0))
        await reading(db, power, 20, 50)
        assert [transition.kind for transition in await evaluate_site_alarms(site_id, at(20))] == ["raise"]

        new_rule = threshold_alarm(power.id, delay_sec=20, value=40).rule  # still violated at 50
        response = await client.put(f"/api/alarms/site/{site_id}/definitions/{alarm.id}",
                                    json=AlarmDefinitionUpdateRequest(rule=new_rule).model_dump(mode="json", exclude_unset=True))
        assert response.status_code == 200, response.text
        (old_event,) = await events(client, site_id)
        assert old_event.cleared_at is not None

        await reading(db, power, 30, 50)
        assert await evaluate_site_alarms(site_id, at(30)) == []  # the delay restarted at the edit
        await reading(db, power, 50, 50)
        (raised,) = await evaluate_site_alarms(site_id, at(50))
        assert (raised.kind, raised.at) == ("raise", at(50))
        assert [event.cleared_at is None for event in await events(client, site_id)] == [True, False]

    async def test_against_another_point(self, client, db):
        site_id, _, (power, other, _) = await site_with_points(client)
        await create_alarm(client, site_id, threshold_alarm(power.id, value=None, compare_point_id=other.id))
        await reading(db, power, 0, 50)
        await reading(db, other, 0, 60)
        assert await evaluate_site_alarms(site_id, at(0)) == []
        await reading(db, power, 10, 70)
        await reading(db, other, 10, 60)
        assert [transition.kind for transition in await evaluate_site_alarms(site_id, at(10))] == ["raise"]

    async def test_a_reading_older_than_the_max_gap_is_missing(self, client, db):
        site_id, _, (power, *_) = await site_with_points(client)
        await create_alarm(client, site_id, threshold_alarm(power.id))
        await reading(db, power, 0, 50)
        stale_by = int(input_max_gap().total_seconds()) + 1
        assert await evaluate_site_alarms(site_id, at(stale_by)) == []
        assert await events(client, site_id) == []

    async def test_a_disabled_alarm_is_not_raised(self, client, db):
        site_id, _, (power, *_) = await site_with_points(client)
        await create_alarm(client, site_id, threshold_alarm(power.id).model_copy(update={"enabled": False}))
        await reading(db, power, 0, 50)
        assert await evaluate_site_alarms(site_id, at(0)) == []


class TestCommsStale:
    async def test_raises_back_dated_and_clears_on_the_next_reading(self, client, db):
        site_id, device_id, (power, *_) = await site_with_points(client)
        await create_alarm(client, site_id, AlarmDefinitionCreateRequest(
            name="comms_lost", severity="fault",
            rule=CommsStaleAlarm(kind="comms_stale", device_id=device_id, stale_after_sec=60),
        ))
        assert await evaluate_site_alarms(site_id, at(0)) == []  # never polled: no data, no alarm

        await reading(db, power, 0, 1)
        assert await evaluate_site_alarms(site_id, at(30)) == []
        (raised,) = await evaluate_site_alarms(site_id, at(90))
        assert (raised.kind, raised.at, raised.device_id) == ("raise", at(60), device_id)

        await reading(db, power, 100, 1)
        (cleared,) = await evaluate_site_alarms(site_id, at(100))
        assert cleared.kind == "clear"
        (event,) = await events(client, site_id)
        assert (event.raised_at, event.cleared_at, event.message) == (at(60), at(100), "comms_lost")


class TestCondition:
    async def test_all_group_raises_and_clears(self, client, db):
        site_id, device_id, (power, _, flags) = await site_with_points(client)
        await create_alarm(client, site_id, AlarmDefinitionCreateRequest(
            name="trip_while_producing", severity="fault",
            rule=ConditionAlarm(kind="condition", when=VirtualConditionGroup(match="all", items=[
                VirtualCondition(point_id=flags.id, operator="bit_set", bit=3),
                VirtualCondition(point_id=power.id, operator=">", value=0),
            ])),
        ))
        await reading(db, flags, 0, 0b1000)
        await reading(db, power, 0, 5)
        (raised,) = await evaluate_site_alarms(site_id, at(0))
        assert (raised.kind, raised.device_id) == ("raise", device_id)

        await reading(db, flags, 10, 0)
        assert [transition.kind for transition in await evaluate_site_alarms(site_id, at(10))] == ["clear"]
