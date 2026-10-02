"""
Unit tests for site_profiles.common.health.

Guards the shared device health check: unknown until the device has reported, unhealthy while
it has an active fault alarm, healthy otherwise. The DB reads are faked at the module boundary.
"""

from datetime import UTC, datetime

import pytest

import site_profiles.common.health as common_health
from schemas.site_profiles import DeviceHealthContext
from unit.site_fixtures import CREATED, make_device, make_site

NOW = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)


def context() -> DeviceHealthContext:
    device = make_device(2, [])
    return DeviceHealthContext(site=make_site(), devices=[device], device=device, now=NOW)


def fake_reads(monkeypatch: pytest.MonkeyPatch, last_reading: datetime | None, active_faults: int) -> None:
    async def last_reading_time(device_id: int) -> datetime | None:
        return last_reading

    async def count_events(device_id: int, severity: str) -> int:
        assert severity == "fault"
        return active_faults

    monkeypatch.setattr(common_health, "get_device_last_reading_time", last_reading_time)
    monkeypatch.setattr(common_health, "count_active_device_events", count_events)


class TestCommonNoActiveFaultAlarm:
    async def test_never_reported_is_unknown(self, monkeypatch: pytest.MonkeyPatch):
        fake_reads(monkeypatch, last_reading=None, active_faults=0)
        verdict = await common_health.common_no_active_fault_alarm(context())
        assert verdict.healthy is None
        assert verdict.reason

    async def test_no_fault_is_healthy(self, monkeypatch: pytest.MonkeyPatch):
        fake_reads(monkeypatch, last_reading=CREATED, active_faults=0)
        assert (await common_health.common_no_active_fault_alarm(context())).healthy is True

    @pytest.mark.parametrize(("faults", "reason"), [(1, "1 active fault alarm"), (3, "3 active fault alarms")])
    async def test_active_fault_is_unhealthy(self, monkeypatch: pytest.MonkeyPatch, faults: int, reason: str):
        fake_reads(monkeypatch, last_reading=CREATED, active_faults=faults)
        verdict = await common_health.common_no_active_fault_alarm(context())
        assert (verdict.healthy, verdict.reason) == (False, reason)
