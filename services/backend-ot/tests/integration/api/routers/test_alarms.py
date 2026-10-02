"""
Integration tests for /api/alarms (a site's alarm definitions).

Guards, against a real database:
- user alarms of every kind (threshold against a value or another point, bit test, condition,
  comms-stale) are created with their rule, and their points/device must be active on the site;
- names are unique per site ignoring case, across user and profile alarms;
- at most 20 alarms per site are enabled (an enabled alarm is evaluated and shown);
- profile alarms appear for a site whose profile declares them, follow profile changes, and accept
  only enabled/notifications;
- deleting a user alarm removes it and all its events permanently; a profile alarm can't be deleted;
- disabling an alarm clears its active event; the schema's CHECKs hold;
- the snapshot returns the alarms, active events plus those cleared within 6 h, and their log;
- the event history returns events overlapping a range, newest first, with filters; 400 on a reversed range, 422 without a UTC offset.
"""

from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import AsyncClient
from pydantic import TypeAdapter

from integration.factories import (
    create_alarm,
    create_device,
    create_site,
    point_request,
    upsert_points,
)
from schemas.api_models import (
    DevicePointResponse,
    SiteUpdateRequest,
    VirtualCondition,
    VirtualConditionGroup,
)
from schemas.api_models.alarms import (
    MAX_ENABLED_ALARMS,
    AlarmDefinitionCreateRequest,
    AlarmDefinitionResponse,
    AlarmDefinitionUpdateRequest,
    AlarmEventResponse,
    AlarmSnapshotResponse,
    CommsStaleAlarm,
    ConditionAlarm,
    ThresholdAlarm,
)
from schemas.tests_models import ApiErrorDetail, ApiErrorResponse

ALARM_LIST = TypeAdapter(list[AlarmDefinitionResponse])
EVENT_LIST = TypeAdapter(list[AlarmEventResponse])


def alarms_url(site_id: int) -> str:
    return f"/api/alarms/site/{site_id}/definitions"


async def site_with_points(
    client: AsyncClient, profile: str | None = None, name: str = "Test Site"
) -> tuple[int, int, list[DevicePointResponse]]:
    """A site with one device and three points: power (float), other_power (float), flags (bitfield)."""
    site = await create_site(client, name=name, **({"profile": profile} if profile else {}))
    device = await create_device(client, site.site_id)
    points = await upsert_points(client, site.site_id, device.device_id, [
        point_request(name="power"),
        point_request(name="other_power", address=110),
        point_request(name="flags", address=120, size=1, data_type="bitfield16", bitfield_detail={"3": "trip"}),
    ])
    return site.site_id, device.device_id, points


def threshold_alarm(name: str, point_id: int, **condition: object) -> AlarmDefinitionCreateRequest:
    return AlarmDefinitionCreateRequest(
        name=name, severity="warning",
        rule=ThresholdAlarm(kind="threshold", condition=VirtualCondition.model_validate(
            {"point_id": point_id, "operator": ">", "value": 10} | condition
        )),
    )


async def list_alarms(client: AsyncClient, site_id: int, **params: str | bool) -> list[AlarmDefinitionResponse]:
    response = await client.get(alarms_url(site_id), params=params)
    assert response.status_code == 200, response.text
    return ALARM_LIST.validate_python(response.json())


async def put(client: AsyncClient, site_id: int, alarm_id: int, **fields: object):
    body = AlarmDefinitionUpdateRequest.model_validate(fields).model_dump(mode="json", exclude_unset=True)
    return await client.put(f"{alarms_url(site_id)}/{alarm_id}", json=body)


def error_message(response) -> str:
    detail = ApiErrorResponse.model_validate(response.json()).detail
    assert isinstance(detail, ApiErrorDetail)
    return detail.message


class TestCreateUserAlarm:
    async def test_threshold_against_a_value_and_against_another_point(self, client):
        site_id, _, (power, other, _) = await site_with_points(client)

        on_value = await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        on_point = await create_alarm(client, site_id, threshold_alarm(
            "power_above_other", power.id, value=None, compare_point_id=other.id,
        ))

        assert (on_value.source, on_value.kind, on_value.profile_alarm_key) == ("USER", "threshold", None)
        assert isinstance(on_point.rule, ThresholdAlarm) and on_point.rule.condition.compare_point_id == other.id
        assert [alarm.name for alarm in await list_alarms(client, site_id)] == ["power_above_other", "power_high"]

    async def test_condition_and_comms_stale(self, client):
        site_id, device_id, (power, _, flags) = await site_with_points(client)
        condition = await create_alarm(client, site_id, AlarmDefinitionCreateRequest(
            name="trip_while_producing", severity="fault",
            rule=ConditionAlarm(kind="condition", delay_sec=30, when=VirtualConditionGroup(match="all", items=[
                VirtualCondition(point_id=flags.id, operator="bit_set", bit=3),
                VirtualCondition(point_id=power.id, operator=">", value=0),
            ])),
        ))
        stale = await create_alarm(client, site_id, AlarmDefinitionCreateRequest(
            name="comms_lost", severity="fault",
            rule=CommsStaleAlarm(kind="comms_stale", device_id=device_id, stale_after_sec=60),
        ))
        assert (condition.kind, stale.kind) == ("condition", "comms_stale")

    async def test_name_clash_ignoring_case_is_409(self, client):
        site_id, _, (power, *_) = await site_with_points(client)
        await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        response = await client.post(alarms_url(site_id), json=threshold_alarm("POWER_HIGH", power.id).model_dump(mode="json"))
        assert response.status_code == 409

    async def test_inputs_must_be_on_the_site_and_bit_tests_need_a_bitfield(self, client):
        site_id, _, (power, *_) = await site_with_points(client)
        _, _, (foreign, *_) = await site_with_points(client, name="Other Site")
        for request in (
            threshold_alarm("x1", 99999),
            threshold_alarm("x2", foreign.id),
            threshold_alarm("x3", power.id, value=None, compare_point_id=foreign.id),
            threshold_alarm("x4", power.id, operator="bit_set", value=None, bit=3),
            AlarmDefinitionCreateRequest(name="x5", severity="fault", rule=CommsStaleAlarm(
                kind="comms_stale", device_id=99999, stale_after_sec=60,
            )),
        ):
            response = await client.post(alarms_url(site_id), json=request.model_dump(mode="json"))
            assert response.status_code == 400, request.name

    async def test_unknown_site_is_404_and_a_malformed_rule_422(self, client):
        site_id, _, (power, *_) = await site_with_points(client)
        assert (await client.post(alarms_url(9999), json=threshold_alarm("a", power.id).model_dump(mode="json"))).status_code == 404
        bad = threshold_alarm("a", power.id).model_dump(mode="json") | {"rule": {"kind": "threshold", "condition": {"point_id": power.id, "operator": ">"}}}
        assert (await client.post(alarms_url(site_id), json=bad)).status_code == 422


class TestEnabledLimit:
    async def test_at_most_twenty_alarms_are_enabled_per_site(self, client):
        site_id, _, (power, *_) = await site_with_points(client)
        for index in range(MAX_ENABLED_ALARMS):
            await create_alarm(client, site_id, threshold_alarm(f"a{index}", power.id))

        one_more = threshold_alarm("a20", power.id)
        response = await client.post(alarms_url(site_id), json=one_more.model_dump(mode="json"))
        assert response.status_code == 409
        assert "disable one first" in error_message(response)

        disabled = await create_alarm(client, site_id, one_more.model_copy(update={"enabled": False}))
        assert (await put(client, site_id, disabled.id, enabled=True)).status_code == 409
        first = (await list_alarms(client, site_id))[0]
        assert (await put(client, site_id, first.id, enabled=False)).status_code == 200
        assert (await put(client, site_id, disabled.id, enabled=True)).status_code == 200
        # Changing anything else on an enabled alarm at the limit is fine.
        assert (await put(client, site_id, disabled.id, enabled=True, message="still enabled")).status_code == 200

    async def test_a_profile_alarm_synced_onto_a_full_site_starts_disabled(self, client):
        site_id, _, (power, *_) = await site_with_points(client)
        for index in range(MAX_ENABLED_ALARMS):
            await create_alarm(client, site_id, threshold_alarm(f"a{index}", power.id))
        to_profile = await client.put(f"/api/sites/{site_id}", json=SiteUpdateRequest(profile="alpha_solar").model_dump(mode="json", exclude_unset=True))
        assert to_profile.status_code == 200, to_profile.text
        (profile_alarm,) = [alarm for alarm in await list_alarms(client, site_id) if alarm.source == "PROFILE"]
        assert profile_alarm.enabled is False


class TestProfileAlarms:
    async def test_a_site_gets_its_profiles_alarms_and_they_follow_profile_changes(self, client):
        site_id, *_ = await site_with_points(client, profile="alpha_solar")
        (profile_alarm,) = await list_alarms(client, site_id)
        assert (profile_alarm.source, profile_alarm.kind, profile_alarm.profile_alarm_key) == ("PROFILE", "profile", "placeholder_profile_alarm_1")
        assert (profile_alarm.name, profile_alarm.severity, profile_alarm.rule) == ("placeholder_profile_alarm_1", "fault", None)

        # An explicit null removes the site's profile.
        no_profile = await client.put(f"/api/sites/{site_id}", json=SiteUpdateRequest(profile=None).model_dump(mode="json", exclude_unset=True))
        assert no_profile.status_code == 200, no_profile.text
        assert await list_alarms(client, site_id) == []
        (retired,) = await list_alarms(client, site_id, include_deleted=True)
        assert retired.deleted_at is not None

        await client.put(f"/api/sites/{site_id}", json=SiteUpdateRequest(profile="alpha_solar").model_dump(mode="json", exclude_unset=True))
        (restored,) = await list_alarms(client, site_id)
        assert restored.id == profile_alarm.id

    async def test_only_enabled_and_notify_change_and_it_cant_be_deleted(self, client):
        site_id, *_ = await site_with_points(client, profile="alpha_solar")
        (profile_alarm,) = await list_alarms(client, site_id)

        changed = await put(client, site_id, profile_alarm.id, enabled=False, notify_email=True)
        assert changed.status_code == 200, changed.text
        assert AlarmDefinitionResponse.model_validate(changed.json()).notify_email is True

        renamed = await put(client, site_id, profile_alarm.id, name="renamed")
        assert renamed.status_code == 400
        assert "only" in error_message(renamed)
        assert (await client.delete(f"{alarms_url(site_id)}/{profile_alarm.id}")).status_code == 400

    async def test_a_user_alarm_cant_take_a_profile_alarms_name(self, client):
        site_id, _, (power, *_) = await site_with_points(client, profile="alpha_solar")
        response = await client.post(alarms_url(site_id), json=threshold_alarm("PLACEHOLDER_PROFILE_ALARM_1", power.id).model_dump(mode="json"))
        assert response.status_code == 409


class TestUpdateAndDelete:
    async def test_update_changes_sent_fields_and_rule_kind(self, client):
        site_id, device_id, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        response = await put(client, site_id, alarm.id, message="now stale-based",
                             rule=CommsStaleAlarm(kind="comms_stale", device_id=device_id, stale_after_sec=30))
        assert response.status_code == 200, response.text
        updated = AlarmDefinitionResponse.model_validate(response.json())
        assert (updated.kind, updated.message, updated.name, updated.severity) == ("comms_stale", "now stale-based", "power_high", "warning")

    async def test_null_for_a_field_is_400_and_unknown_alarm_404(self, client):
        site_id, _, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        response = await client.put(f"{alarms_url(site_id)}/{alarm.id}", json={"enabled": None})
        assert response.status_code == 400
        assert (await put(client, site_id, 99999, enabled=False)).status_code == 404

    async def test_delete_removes_the_alarm_and_its_history_permanently(self, client, db):
        site_id, _, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm("power_high", power.id).model_copy(update={"notify_email": True}))
        for raised_at, cleared_at in [
            (datetime(2026, 9, 30, 9, 0, tzinfo=UTC), datetime(2026, 9, 30, 9, 30, tzinfo=UTC)),
            (datetime(2026, 9, 30, 10, 0, tzinfo=UTC), None),
        ]:
            await db.execute(
                "INSERT INTO alarm_events (definition_id, site_id, severity, raised_at, cleared_at) VALUES ($1, $2, 'warning', $3, $4)",
                alarm.id, site_id, raised_at, cleared_at,
            )

        response = await client.delete(f"{alarms_url(site_id)}/{alarm.id}")
        assert response.status_code == 200, response.text
        deleted = AlarmDefinitionResponse.model_validate(response.json())
        assert (deleted.id, deleted.name, deleted.notify_email) == (alarm.id, "power_high", True)  # as it was
        assert await list_alarms(client, site_id, include_deleted=True) == []
        assert await db.fetchval("SELECT count(*) FROM alarm_definitions WHERE id = $1", alarm.id) == 0
        assert await db.fetchval("SELECT count(*) FROM alarm_events WHERE definition_id = $1", alarm.id) == 0
        # The name is free again, and the deleted alarm is gone for updates and deletes.
        await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        assert (await put(client, site_id, alarm.id, enabled=False)).status_code == 404
        assert (await client.delete(f"{alarms_url(site_id)}/{alarm.id}")).status_code == 404

    async def test_disabling_clears_the_active_event(self, client, db):
        site_id, _, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        await db.execute(
            "INSERT INTO alarm_events (definition_id, site_id, severity, raised_at) VALUES ($1, $2, 'warning', now())",
            alarm.id, site_id,
        )
        assert (await put(client, site_id, alarm.id, enabled=False)).status_code == 200
        assert await db.fetchval("SELECT count(*) FROM alarm_events WHERE definition_id = $1 AND cleared_at IS NULL", alarm.id) == 0

    @staticmethod
    async def active_alarm_with_timer(client, db) -> tuple[int, AlarmDefinitionResponse]:
        """A threshold alarm with an active event and a running delay timer."""
        site_id, _, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        await db.execute(
            "INSERT INTO alarm_events (definition_id, site_id, severity, raised_at) VALUES ($1, $2, 'warning', now())",
            alarm.id, site_id,
        )
        await db.execute(
            "INSERT INTO alarm_evaluation_state (definition_id, condition_since, last_evaluated_at) VALUES ($1, now(), now())",
            alarm.id,
        )
        return site_id, alarm

    @staticmethod
    async def active_and_timer(db, alarm_id: int) -> tuple[int, int]:
        active = await db.fetchval("SELECT count(*) FROM alarm_events WHERE definition_id = $1 AND cleared_at IS NULL", alarm_id)
        timers = await db.fetchval("SELECT count(*) FROM alarm_evaluation_state WHERE definition_id = $1", alarm_id)
        return active, timers

    async def test_changing_the_rule_clears_the_active_event_and_restarts_the_delay(self, client, db):
        site_id, alarm = await self.active_alarm_with_timer(client, db)
        assert isinstance(alarm.rule, ThresholdAlarm)
        changed = alarm.rule.model_copy(update={"delay_sec": 30, "condition": alarm.rule.condition.model_copy(update={"value": 50})})

        response = await put(client, site_id, alarm.id, rule=changed)
        assert response.status_code == 200, response.text
        assert await self.active_and_timer(db, alarm.id) == (0, 0)
        updated = AlarmDefinitionResponse.model_validate(response.json())
        assert isinstance(updated.rule, ThresholdAlarm) and (updated.rule.condition.value, updated.rule.delay_sec) == (50, 30)

    async def test_the_same_rule_or_other_fields_keep_the_active_event(self, client, db):
        site_id, alarm = await self.active_alarm_with_timer(client, db)
        response = await put(client, site_id, alarm.id, rule=alarm.rule, name="power_very_high", severity="fault", message="hot")
        assert response.status_code == 200, response.text
        assert await self.active_and_timer(db, alarm.id) == (1, 1)


class TestSchema:
    async def test_checks_reject_inconsistent_rows(self, client, db):
        site_id, *_ = await site_with_points(client)
        with pytest.raises(asyncpg.CheckViolationError):  # a user alarm needs its rule
            await db.execute(
                "INSERT INTO alarm_definitions (site_id, source, name, kind, severity) VALUES ($1, 'USER', 'n', 'threshold', 'fault')",
                site_id,
            )
        with pytest.raises(asyncpg.CheckViolationError):  # a profile alarm has no rule, and a key
            await db.execute(
                "INSERT INTO alarm_definitions (site_id, source, name, kind, severity, rule) VALUES ($1, 'PROFILE', 'n', 'profile', 'fault', '{}')",
                site_id,
            )


async def insert_event(db, definition_id: int, site_id: int, raised_at: datetime, cleared_at: datetime | None,
                       device_id: int | None = None, severity: str = "warning") -> int:
    return await db.fetchval(
        "INSERT INTO alarm_events (definition_id, site_id, device_id, severity, raised_at, cleared_at, message)"
        " VALUES ($1, $2, $3, $4, $5, $6, 'Power high') RETURNING id",
        definition_id, site_id, device_id, severity, raised_at, cleared_at,
    )


class TestSnapshot:
    async def test_definitions_active_and_recent_events_and_the_log(self, client, db):
        site_id, _, (power, *_) = await site_with_points(client)
        alarm = await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        now = datetime.now(UTC)
        active = await insert_event(db, alarm.id, site_id, now - timedelta(minutes=5), None)
        recent = await insert_event(db, alarm.id, site_id, now - timedelta(hours=2), now - timedelta(hours=1))
        await insert_event(db, alarm.id, site_id, now - timedelta(hours=9), now - timedelta(hours=8))  # too old

        response = await client.get(f"/api/alarms/site/{site_id}/snapshot")
        assert response.status_code == 200, response.text
        snapshot = AlarmSnapshotResponse.model_validate(response.json())
        assert snapshot.site_id == site_id and abs(snapshot.now - now) < timedelta(minutes=1)
        assert [definition.id for definition in snapshot.definitions] == [alarm.id]
        assert [event.id for event in snapshot.events] == [active, recent]
        assert [(entry.id, entry.message) for entry in snapshot.log] == [
            (f"{active}:raised", "Power high"),
            (f"{recent}:cleared", "power_high cleared"),
            (f"{recent}:raised", "Power high"),
        ]

    async def test_unknown_site_is_404(self, client):
        assert (await client.get("/api/alarms/site/9999/snapshot")).status_code == 404


class TestEventHistory:
    START = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
    END = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

    async def query(self, client: AsyncClient, site_id: int, **params: object):
        return await client.get(f"/api/alarms/site/{site_id}/events", params={
            "start_time": self.START.isoformat(), "end_time": self.END.isoformat(), **params,
        })

    async def test_overlap_newest_first_and_filters(self, client, db):
        site_id, device_id, (power, other, _) = await site_with_points(client)
        first = await create_alarm(client, site_id, threshold_alarm("power_high", power.id))
        second = await create_alarm(client, site_id, threshold_alarm("other_high", other.id))
        hour = timedelta(hours=1)
        spans_start = await insert_event(db, first.id, site_id, self.START - hour, self.START + hour, device_id=device_id)
        still_active = await insert_event(db, second.id, site_id, self.START - 5 * hour, None, severity="fault")
        inside = await insert_event(db, first.id, site_id, self.START + hour, self.START + 2 * hour)
        await insert_event(db, first.id, site_id, self.START - 3 * hour, self.START - 2 * hour)  # before
        await insert_event(db, second.id, site_id, self.END + hour, self.END + 2 * hour)  # after

        async def ids(**params: object) -> list[int]:
            response = await self.query(client, site_id, **params)
            assert response.status_code == 200, response.text
            return [event.id for event in EVENT_LIST.validate_python(response.json())]

        assert await ids() == [inside, spans_start, still_active]
        assert await ids(device_id=device_id) == [spans_start]
        assert await ids(severity="fault") == [still_active]
        assert await ids(definition_id=first.id) == [inside, spans_start]

    async def test_bad_range_and_unknown_site(self, client):
        site_id, *_ = await site_with_points(client)
        reversed_range = await client.get(f"/api/alarms/site/{site_id}/events", params={
            "start_time": self.END.isoformat(), "end_time": self.START.isoformat(),
        })
        assert reversed_range.status_code == 400  # the service-wide time-range middleware
        no_offset = await client.get(f"/api/alarms/site/{site_id}/events", params={
            "start_time": "2026-09-30T10:00:00", "end_time": "2026-09-30T12:00:00",
        })
        assert no_offset.status_code == 422
        assert (await self.query(client, 9999)).status_code == 404
