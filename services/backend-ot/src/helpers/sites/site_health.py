"""
Which ALARM-class points of a site's devices are set (GET /api/sites/{site_id}/health).

Pure: the controller loads the devices and the points' latest readings and passes them in.
A point is set when its latest reading is non-zero; one that has never reported is unknown.
"""

from collections.abc import Collection, Iterable

from helpers.reads.calculate_reads import translate_bitfield_to_named_map, translate_enum_value
from schemas.api_models import (
    ActivePointAlarm,
    AlarmCounts,
    DeviceAlarmStatus,
    DevicePointResponse,
    DeviceWithPoints,
    Severity,
)
from schemas.internal_models import PointReading

# Highest first: the order highest_severity picks from.
SEVERITY_ORDER: tuple[Severity, ...] = ("HIGH", "MEDIUM", "LOW")


def alarm_points(
    device: DeviceWithPoints, severities: Collection[Severity] | None = None
) -> list[DevicePointResponse]:
    """The device's ALARM-class points (every category) to evaluate. With no severity filter
    (None or empty) that is all of them, including points without a severity; otherwise only
    those whose severity is in it."""
    points = device.points.standardized + device.points.native + device.points.virtual
    return [
        point
        for point in points
        if point.point_class == "ALARM" and (not severities or point.severity in severities)
    ]


def is_alarm_set(reading: PointReading) -> bool:
    """True when the point has reported and its latest value is non-zero."""
    return reading.timestamp is not None and reading.derived_value is not None and reading.derived_value != 0


def active_point_alarm(point: DevicePointResponse, reading: PointReading) -> ActivePointAlarm | None:
    """The point as an active alarm, or None when it isn't set."""
    if not is_alarm_set(reading) or reading.timestamp is None or reading.derived_value is None:
        return None
    active_bits: list[str] = []
    if point.bitfield_detail:
        bit_states = translate_bitfield_to_named_map(reading.derived_value, point.bitfield_detail)
        active_bits = [label for label, state in bit_states.items() if state]
    enum_label = translate_enum_value(reading.derived_value, point.enum_detail) if point.enum_detail else None
    return ActivePointAlarm(
        device_point_id=point.id,
        device_point_name=point.name,
        severity=point.severity,
        value=reading.derived_value,
        active_bits=active_bits,
        enum_label=enum_label,
        timestamp=reading.timestamp,
    )


def highest_severity(severities: Iterable[Severity | None]) -> Severity | None:
    """The highest of the given severities (HIGH > MEDIUM > LOW); None when there is none."""
    present = set(severities)
    return next((severity for severity in SEVERITY_ORDER if severity in present), None)


def device_alarm_status(
    device: DeviceWithPoints,
    readings_by_point: dict[int, PointReading],
    severities: Collection[Severity] | None = None,
) -> DeviceAlarmStatus:
    """The device's set ALARM points (filtered by severity) and their counts. A point without a
    reading in `readings_by_point`, or one that has never reported, counts as unknown."""
    active_alarms: list[ActivePointAlarm] = []
    unknown_count = 0
    for point in alarm_points(device, severities):
        reading = readings_by_point.get(point.id)
        if reading is None or reading.timestamp is None:
            unknown_count += 1
            continue
        active = active_point_alarm(point, reading)
        if active is not None:
            active_alarms.append(active)
    counts = rollup_counts(
        [alarm.severity for alarm in active_alarms], unknown_count=unknown_count
    )
    return DeviceAlarmStatus(
        device_id=device.device_id,
        device_name=device.name,
        active_alarms=active_alarms,
        **counts.model_dump(),
    )


def rollup_counts(active_severities: list[Severity | None], unknown_count: int = 0) -> AlarmCounts:
    """Counts per severity of the set points; a point without a severity is in none of them."""
    return AlarmCounts(
        highest_severity=highest_severity(active_severities),
        high_count=active_severities.count("HIGH"),
        medium_count=active_severities.count("MEDIUM"),
        low_count=active_severities.count("LOW"),
        unknown_count=unknown_count,
    )


def site_alarm_counts(devices: list[DeviceAlarmStatus]) -> AlarmCounts:
    """The devices' counts summed into the site's."""
    return AlarmCounts(
        highest_severity=highest_severity(device.highest_severity for device in devices),
        high_count=sum(device.high_count for device in devices),
        medium_count=sum(device.medium_count for device in devices),
        low_count=sum(device.low_count for device in devices),
        unknown_count=sum(device.unknown_count for device in devices),
    )
