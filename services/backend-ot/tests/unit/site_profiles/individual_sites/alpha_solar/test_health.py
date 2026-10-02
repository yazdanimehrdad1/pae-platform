"""
Unit tests for site_profiles.individual_sites.alpha_solar.health.

Guards the BESS health check: it starts from the common check (unknown or unhealthy wins), then
is unhealthy if battery_state or bms_state reads 'fault' (any case), and keeps the common verdict
when the state points are missing or unread. Reads are faked at the module boundary.
"""

from datetime import UTC, datetime

import pytest

import site_profiles.individual_sites.alpha_solar.health as alpha_health
from schemas.api_models import DeviceHealth
from schemas.internal_models import PointReading
from schemas.site_profiles import DeviceHealthContext
from unit.site_fixtures import make_device, make_point, make_reading, make_site

NOW = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
BATTERY_STATES = {"0": "standby", "1": "charging", "4": "FAULT"}
BMS_STATES = {"0": "idle", "5": "fault"}


def context(*point_names: str) -> DeviceHealthContext:
    device = make_device(2, [make_point(20 + index, 2, name) for index, name in enumerate(point_names)])
    return DeviceHealthContext(site=make_site(), devices=[device], device=device, now=NOW)


def fake(
    monkeypatch: pytest.MonkeyPatch,
    common: DeviceHealth,
    readings: dict[int, tuple[float | None, dict[str, str]]],
) -> None:
    async def common_check(ctx: DeviceHealthContext) -> DeviceHealth:
        return common

    async def latest(point_ids: list[int], site_id: int | None = None) -> list[PointReading]:
        return [
            make_reading(point_id, readings[point_id][0], enum_detail=readings[point_id][1], name=f"p{point_id}")
            for point_id in point_ids
        ]

    monkeypatch.setattr(alpha_health, "common_no_active_fault_alarm", common_check)
    monkeypatch.setattr(alpha_health, "get_latest_readings_by_point_ids", latest)


class TestBessHealth:
    async def test_unknown_common_verdict_wins(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, DeviceHealth(healthy=None, reason="No readings"), {})
        assert (await alpha_health.bess_health(context("battery_state"))).healthy is None

    async def test_active_fault_alarm_wins(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, DeviceHealth(healthy=False, reason="1 active fault alarm"), {})
        assert (await alpha_health.bess_health(context("battery_state"))).healthy is False

    async def test_battery_state_fault_is_unhealthy_whatever_the_case(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, DeviceHealth(healthy=True), {20: (4.0, BATTERY_STATES), 21: (0.0, BMS_STATES)})
        verdict = await alpha_health.bess_health(context("battery_state", "bms_state"))
        assert verdict.healthy is False
        assert "fault" in (verdict.reason or "")

    async def test_bms_state_fault_is_unhealthy(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, DeviceHealth(healthy=True), {20: (1.0, BATTERY_STATES), 21: (5.0, BMS_STATES)})
        assert (await alpha_health.bess_health(context("battery_state", "bms_state"))).healthy is False

    async def test_normal_states_are_healthy(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, DeviceHealth(healthy=True), {20: (1.0, BATTERY_STATES), 21: (0.0, BMS_STATES)})
        assert (await alpha_health.bess_health(context("battery_state", "bms_state"))).healthy is True

    async def test_missing_or_unread_state_points_keep_the_common_verdict(self, monkeypatch: pytest.MonkeyPatch):
        fake(monkeypatch, DeviceHealth(healthy=True), {20: (None, BATTERY_STATES)})
        assert (await alpha_health.bess_health(context("battery_state"))).healthy is True
        assert (await alpha_health.bess_health(context())).healthy is True
