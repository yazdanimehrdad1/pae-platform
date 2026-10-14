"""
Unit tests for helpers.sites.site_health.

Guards what counts as a set ALARM point (reported and non-zero; never reported is unknown, not
set), the detail reported for it (named bits of a bitfield, the enum label), the severity filter
(empty means all, including points without a severity) and the rollups (HIGH > MEDIUM > LOW, a
point without a severity listed but in no count, the site summing its devices).
"""

from helpers.sites.site_health import (
    active_point_alarm,
    alarm_points,
    device_alarm_status,
    highest_severity,
    is_alarm_set,
    site_alarm_counts,
)
from schemas.api_models import DevicePointResponse, DeviceWithPoints
from schemas.internal_models import PointReading
from unit.site_fixtures import CREATED, make_device, make_point, make_reading


def alarm_point(
    point_id: int,
    severity: str | None,
    device_id: int = 1,
    point_class: str = "ALARM",
    bitfield_detail: dict[str, str] | None = None,
    enum_detail: dict[str, str] | None = None,
) -> DevicePointResponse:
    return make_point(point_id, device_id, f"point_{point_id}").model_copy(
        update={
            "point_class": point_class,
            "severity": severity,
            "bitfield_detail": bitfield_detail,
            "enum_detail": enum_detail,
        }
    )


def readings(*pairs: tuple[int, float | None]) -> dict[int, PointReading]:
    return {point_id: make_reading(point_id, value) for point_id, value in pairs}


def device_with(*points: DevicePointResponse, device_id: int = 1) -> DeviceWithPoints:
    return make_device(device_id, list(points))


class TestIsAlarmSet:
    def test_non_zero_is_set(self):
        assert is_alarm_set(make_reading(1, 1.0))
        assert is_alarm_set(make_reading(1, -2.0))

    def test_zero_is_not_set(self):
        assert not is_alarm_set(make_reading(1, 0.0))

    def test_never_reported_is_not_set(self):
        assert not is_alarm_set(make_reading(1, None))


class TestActivePointAlarm:
    def test_bitfield_lists_the_named_bits_that_are_set_in_bit_order(self):
        point = alarm_point(1, "HIGH", bitfield_detail={"0": "COMM_ERROR", "1": "OVER_TEMP", "3": "GROUND_FAULT"})
        active = active_point_alarm(point, make_reading(1, 0b1001))
        assert active is not None
        assert active.active_bits == ["COMM_ERROR", "GROUND_FAULT"]
        assert (active.device_point_name, active.value, active.severity, active.timestamp) == ("point_1", 9.0, "HIGH", CREATED)

    def test_enum_reports_its_label(self):
        point = alarm_point(1, "MEDIUM", enum_detail={"0": "OK", "2": "TRIPPED"})
        active = active_point_alarm(point, make_reading(1, 2))
        assert active is not None
        assert (active.enum_label, active.active_bits) == ("TRIPPED", [])

    def test_unset_point_is_none(self):
        assert active_point_alarm(alarm_point(1, "LOW"), make_reading(1, 0)) is None


class TestAlarmPoints:
    device = device_with(
        alarm_point(1, "HIGH"),
        alarm_point(2, "LOW"),
        alarm_point(3, None),
        alarm_point(4, "HIGH", point_class="ANALOG"),
    )

    def test_non_alarm_points_are_ignored(self):
        assert [point.id for point in alarm_points(self.device)] == [1, 2, 3]

    def test_empty_filter_means_all_including_points_without_severity(self):
        assert [point.id for point in alarm_points(self.device, [])] == [1, 2, 3]

    def test_filter_keeps_only_matching_severities(self):
        assert [point.id for point in alarm_points(self.device, ["LOW"])] == [2]

    def test_virtual_and_standardized_points_are_included(self):
        device = device_with(alarm_point(1, "HIGH"))
        device.points.virtual.append(alarm_point(5, "LOW"))
        device.points.standardized.append(alarm_point(6, "MEDIUM"))
        assert sorted(point.id for point in alarm_points(device)) == [1, 5, 6]


class TestHighestSeverity:
    def test_high_beats_medium_beats_low(self):
        assert highest_severity(["LOW", "HIGH", "MEDIUM"]) == "HIGH"
        assert highest_severity(["LOW", "MEDIUM"]) == "MEDIUM"

    def test_none_when_nothing_has_a_severity(self):
        assert highest_severity([None]) is None
        assert highest_severity([]) is None


class TestDeviceAlarmStatus:
    def test_counts_set_points_per_severity(self):
        device = device_with(alarm_point(1, "HIGH"), alarm_point(2, "LOW"), alarm_point(3, "LOW"), alarm_point(4, "MEDIUM"))
        status = device_alarm_status(device, readings((1, 1), (2, 1), (3, 1), (4, 0)))
        assert [alarm.device_point_id for alarm in status.active_alarms] == [1, 2, 3]
        assert (status.highest_severity, status.high_count, status.medium_count, status.low_count) == ("HIGH", 1, 0, 2)
        assert (status.device_id, status.device_name) == (1, "device_1")

    def test_no_set_points_is_clean(self):
        status = device_alarm_status(device_with(alarm_point(1, "HIGH")), readings((1, 0)))
        assert status.active_alarms == []
        assert (status.highest_severity, status.high_count, status.unknown_count) == (None, 0, 0)

    def test_never_reported_or_missing_reading_is_unknown(self):
        device = device_with(alarm_point(1, "HIGH"), alarm_point(2, "LOW"))
        status = device_alarm_status(device, readings((1, None)))
        assert (status.unknown_count, status.active_alarms) == (2, [])

    def test_point_without_severity_is_listed_but_in_no_count(self):
        status = device_alarm_status(device_with(alarm_point(1, None)), readings((1, 1)))
        assert [alarm.device_point_id for alarm in status.active_alarms] == [1]
        assert (status.highest_severity, status.high_count, status.medium_count, status.low_count) == (None, 0, 0, 0)

    def test_severity_filter_limits_what_is_evaluated(self):
        device = device_with(alarm_point(1, "HIGH"), alarm_point(2, "LOW"), alarm_point(3, None))
        status = device_alarm_status(device, readings((1, 1), (2, 1), (3, 1)), ["LOW"])
        assert [alarm.device_point_id for alarm in status.active_alarms] == [2]
        assert (status.highest_severity, status.high_count, status.low_count) == ("LOW", 0, 1)


class TestSiteAlarmCounts:
    def test_sums_the_devices(self):
        first = device_alarm_status(device_with(alarm_point(1, "LOW"), alarm_point(2, "HIGH")), readings((1, 1), (2, None)))
        second = device_alarm_status(
            device_with(alarm_point(3, "MEDIUM", device_id=2), alarm_point(4, "LOW", device_id=2), device_id=2),
            readings((3, 1), (4, 1)),
        )
        counts = site_alarm_counts([first, second])
        assert (counts.highest_severity, counts.high_count, counts.medium_count, counts.low_count, counts.unknown_count) == (
            "MEDIUM", 0, 1, 2, 1,
        )

    def test_no_devices_is_clean(self):
        counts = site_alarm_counts([])
        assert (counts.highest_severity, counts.high_count, counts.unknown_count) == (None, 0, 0)
