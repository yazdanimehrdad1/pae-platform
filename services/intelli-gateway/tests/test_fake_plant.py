"""The fake plant model hangs together: tests and demos rely on these behaviours."""

from datetime import timedelta

from fakes import FIXED_NOW

from intelli_gateway.fake_data.knowledge_store import InMemoryKnowledgeStore
from intelli_gateway.fake_data.site_data import FakeSiteDataConnector


class TestPlantModelAtMidday:
    """At FIXED_NOW (13:00 local in June) INV2's cabinet is above 60 degC, so it derates."""

    async def test_inv2_derates_and_inv1_runs(self, site_data: FakeSiteDataConnector) -> None:
        latest = await site_data.get_latest_many(
            1, ["INV1.Status", "INV2.Status", "INV2.CabinetTemp", "INV2.ActivePower"]
        )
        inv1, inv2, temp, power = (latest[name] for name in latest)
        assert inv1 is not None and inv1.label == "RUNNING"
        assert inv2 is not None and inv2.label == "DERATED"
        assert temp is not None and isinstance(temp.value, float) and temp.value > 60
        assert power is not None and power.value == 1500.0  # capped while derated

    async def test_alarm_word_sets_over_temp_bit(self, site_data: FakeSiteDataConnector) -> None:
        reading = (await site_data.get_latest_many(1, ["INV2.AlarmWord"]))["INV2.AlarmWord"]
        assert reading is not None
        assert reading.value == 16
        assert reading.active_bits == ["OVER_TEMP"]

    async def test_poi_is_the_sum_of_its_sources(self, site_data: FakeSiteDataConnector) -> None:
        latest = await site_data.get_latest_many(
            1, ["INV1.ActivePower", "INV2.ActivePower", "BESS1.ActivePower", "POI.ActivePower"]
        )
        inv1, inv2, bess, poi = (latest[name] for name in latest)
        assert inv1 and inv2 and bess and poi
        parts = [inv1.value, inv2.value, bess.value]
        assert all(isinstance(part, float) for part in parts)
        assert poi.value == round(0.98 * sum(float(part or 0) for part in parts), 2)

    async def test_battery_charges_at_midday(self, site_data: FakeSiteDataConnector) -> None:
        reading = (await site_data.get_latest_many(1, ["BESS1.State"]))["BESS1.State"]
        assert reading is not None and reading.label == "CHARGING"


class TestStateChanges:
    async def test_daily_cycle_of_inv2(self, site_data: FakeSiteDataConnector) -> None:
        changes = await site_data.get_state_changes(
            1, "INV2.Status", FIXED_NOW - timedelta(days=1), FIXED_NOW
        )
        assert changes is not None
        assert [change.label for change in changes] == [
            "DERATED",
            "SLEEPING",
            "RUNNING",
            "DERATED",
        ]

    async def test_unknown_point(self, site_data: FakeSiteDataConnector) -> None:
        assert (
            await site_data.get_state_changes(1, "NOPE", FIXED_NOW - timedelta(hours=1), FIXED_NOW)
            is None
        )


class TestAlarms:
    async def test_active_alarms(self, site_data: FakeSiteDataConnector) -> None:
        active = await site_data.get_active_alarms(1)
        assert [event.alarm_name for event in active.events] == ["INV2 over-temperature"]
        assert active.events[0].cleared_at is None
        assert [alarm.point_name for alarm in active.point_alarms] == ["INV2.AlarmWord"]

    async def test_history_replays_the_daily_alarm_and_the_one_off_event(
        self, site_data: FakeSiteDataConnector
    ) -> None:
        events = await site_data.get_alarm_events(1, FIXED_NOW - timedelta(days=3), FIXED_NOW)
        names = [event.alarm_name for event in events]
        assert names.count("INV2 over-temperature") == 4
        assert "WS1 communication lost" in names
        assert all(event.cleared_at for event in events[:-1])
        assert [event.raised_at for event in events] == sorted(event.raised_at for event in events)

    async def test_device_filter(self, site_data: FakeSiteDataConnector) -> None:
        events = await site_data.get_alarm_events(
            1, FIXED_NOW - timedelta(days=3), FIXED_NOW, device_id=40
        )
        assert [event.alarm_name for event in events] == ["WS1 communication lost"]


class TestStaleDevice:
    async def test_wtg2_stopped_reporting(self, site_data: FakeSiteDataConnector) -> None:
        latest = await site_data.get_latest_many(2, ["WTG1.ActivePower", "WTG2.ActivePower"])
        wtg1, wtg2 = latest["WTG1.ActivePower"], latest["WTG2.ActivePower"]
        assert wtg1 is not None and not wtg1.stale
        assert wtg2 is not None and wtg2.stale and wtg2.age_s == 3 * 3600
        comms = {entry.device_id: entry.stale for entry in await site_data.get_device_comms(2)}
        assert comms == {100: False, 101: True, 110: False}

    async def test_history_ends_at_the_last_reading(self, site_data: FakeSiteDataConnector) -> None:
        samples = await site_data.get_history(
            2, "WTG2.ActivePower", FIXED_NOW - timedelta(hours=6), FIXED_NOW
        )
        assert samples is not None
        assert samples[-1].timestamp == FIXED_NOW - timedelta(hours=3)


class TestKnowledgeStore:
    async def test_guides_are_per_site_device(
        self, knowledge_store: InMemoryKnowledgeStore
    ) -> None:
        guide = await knowledge_store.get_point_guide(1, 11, "INV2.Status")
        assert guide is not None and guide.find_state(code=4) is not None
        assert await knowledge_store.get_point_guide(1, 10, "INV2.Status") is None

    async def test_notes_found_by_linked_point_and_filtered_by_device(
        self, knowledge_store: InMemoryKnowledgeStore
    ) -> None:
        by_point = await knowledge_store.search_notes(1, ["INV2.AlarmWord"], 10)
        assert [note.title for note in by_point] == ["INV2 derating on warm days"]
        other_device = await knowledge_store.search_notes(1, ["INV2"], 10, device_id=40)
        assert other_device == []
