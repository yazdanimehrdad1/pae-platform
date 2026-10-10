"""
Unit tests for site_profiles.individual_sites.alpha_solar.alpha_solar_alarms.

Guards high_severity_alarm_point_active: active while any HIGH ALARM-class point on any device
reads non-zero and fresh; value is how many are set; device_id is their device only when they are
all on one. MEDIUM/LOW, non-ALARM, never-reported and stale points don't count, and a site
without HIGH alarm points is never active and reads nothing. Reads are faked at the module boundary.
"""

from datetime import UTC, datetime, timedelta

import pytest

import site_profiles.individual_sites.alpha_solar.alpha_solar_alarms as alpha_alarms
from helpers.virtual_points.resolve import input_max_gap
from schemas.api_models import DevicePointResponse
from schemas.internal_models import PointReading
from schemas.site_profiles import AlarmContext
from unit.site_fixtures import make_device, make_point, make_reading, make_site

NOW = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
FRESH = NOW - timedelta(seconds=5)


def alarm_point(point_id: int, device_id: int, severity: str | None = "HIGH", point_class: str = "ALARM") -> DevicePointResponse:
    return make_point(point_id, device_id, f"p{point_id}").model_copy(
        update={"point_class": point_class, "severity": severity}
    )


def context(*devices: tuple[int, list[DevicePointResponse]]) -> AlarmContext:
    return AlarmContext(
        site=make_site(), devices=[make_device(device_id, points) for device_id, points in devices], now=NOW
    )


def fake(
    monkeypatch: pytest.MonkeyPatch, values: dict[int, float | None], at: datetime = FRESH
) -> list[list[int]]:
    """Fake the latest readings: `values` by point id (None = never reported). Returns the calls."""
    calls: list[list[int]] = []

    async def latest(point_ids: list[int], site_id: int | None = None) -> list[PointReading]:
        calls.append(point_ids)
        readings = [make_reading(point_id, values.get(point_id)) for point_id in point_ids]
        return [
            reading.model_copy(update={"timestamp": at}) if reading.timestamp is not None else reading
            for reading in readings
        ]

    monkeypatch.setattr(alpha_alarms, "get_latest_readings_by_point_ids", latest)
    return calls


class TestHighSeverityAlarmPointActive:
    async def test_one_high_point_set_is_active_on_its_device(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {20: 1.0, 21: 0.0})
        check = await alpha_alarms.high_severity_alarm_point_active(
            context((2, [alarm_point(20, 2), alarm_point(21, 2)]))
        )
        assert (check.active, check.value, check.device_id) == (True, 1, 2)

    async def test_high_points_set_on_two_devices_is_site_level(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {20: 1.0, 30: 4.0})
        check = await alpha_alarms.high_severity_alarm_point_active(
            context((2, [alarm_point(20, 2)]), (3, [alarm_point(30, 3)]))
        )
        assert (check.active, check.value, check.device_id) == (True, 2, None)

    async def test_high_points_all_zero_is_not_active(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {20: 0.0, 30: 0.0})
        check = await alpha_alarms.high_severity_alarm_point_active(
            context((2, [alarm_point(20, 2)]), (3, [alarm_point(30, 3)]))
        )
        assert (check.active, check.value, check.device_id) == (False, 0, None)

    async def test_lower_severity_or_non_alarm_points_dont_count(self, monkeypatch: pytest.MonkeyPatch):
        calls = fake(monkeypatch, {20: 1.0, 21: 1.0, 22: 1.0, 23: 1.0, 24: 0.0})
        check = await alpha_alarms.high_severity_alarm_point_active(
            context((2, [
                alarm_point(20, 2, severity="MEDIUM"),
                alarm_point(21, 2, severity="LOW"),
                alarm_point(22, 2, severity=None),
                alarm_point(23, 2, point_class="ANALOG"),
                alarm_point(24, 2),
            ]))
        )
        assert check.active is False
        assert calls == [[24]]  # only the HIGH ALARM point is read

    async def test_a_never_reported_high_point_is_not_set(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {20: None})
        check = await alpha_alarms.high_severity_alarm_point_active(context((2, [alarm_point(20, 2)])))
        assert check.active is False

    async def test_a_stale_high_point_is_not_set(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, {20: 1.0}, at=NOW - input_max_gap() - timedelta(seconds=1))
        check = await alpha_alarms.high_severity_alarm_point_active(context((2, [alarm_point(20, 2)])))
        assert check.active is False

    async def test_no_high_alarm_points_is_not_active_and_reads_nothing(self, monkeypatch: pytest.MonkeyPatch):
        calls = fake(monkeypatch, {})
        check = await alpha_alarms.high_severity_alarm_point_active(
            context((2, [alarm_point(20, 2, severity="LOW")]))
        )
        assert check == alpha_alarms.AlarmCheck(active=False)
        assert calls == []
