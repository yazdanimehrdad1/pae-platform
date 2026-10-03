"""
Single line diagram logic that needs no I/O: checking an SLD's device links against the site's
devices, and turning point readings into an element's info-box values.
"""

from helpers.reads.calculate_reads import translate_enum_value
from schemas.api_models import (
    SLD_ROLES_BY_NODE_TYPE,
    DeviceWithPoints,
    SiteSld,
    SldNode,
    SldRole,
    SldValue,
)
from schemas.internal_models import PointReading
from site_profiles.common.calculations import POWER_UNIT_TO_KW

# Roles whose value is shown in kW whatever the point's power unit (W, kW, MW).
_POWER_ROLES: frozenset[SldRole] = frozenset({"power"})


def sld_link_errors(sld: SiteSld, devices: list[DeviceWithPoints]) -> list[str]:
    """
    Every device link that doesn't resolve on this site: an unknown (or deleted) device, or a
    point that isn't one of that device's points. Empty when all links resolve.
    """
    points_by_device = {
        device.device_id: {
            point.id
            for point in device.points.standardized + device.points.native + device.points.virtual
        }
        for device in devices
    }
    errors: list[str] = []
    for node in sld.nodes:
        if node.device is None:
            continue
        device_points = points_by_device.get(node.device.device_id)
        if device_points is None:
            errors.append(f"node '{node.id}': device {node.device.device_id} is not a device of this site")
            continue
        for role, point_id in node.device.points.items():
            if point_id not in device_points:
                errors.append(
                    f"node '{node.id}': {role} point {point_id} is not a point of device {node.device.device_id}"
                )
    return errors


def sld_value(role: SldRole, reading: PointReading) -> SldValue:
    """One role's value from its point's latest reading: power in kW, enums with their label."""
    value = reading.derived_value
    unit = reading.unit
    if role in _POWER_ROLES and unit in POWER_UNIT_TO_KW:
        value = None if value is None else value * POWER_UNIT_TO_KW[unit]
        unit = "kW"
    label = None
    if value is not None and reading.enum_detail:
        label = translate_enum_value(value, reading.enum_detail)
    return SldValue(
        point_id=reading.device_point_id,
        value=value,
        label=label,
        unit=unit,
        time=reading.timestamp,
    )


def node_role_values(node: SldNode, readings_by_point: dict[int, PointReading]) -> dict[SldRole, SldValue | None]:
    """Every role of the node's type, in display order: its value, or None when the role is unmapped
    or its point no longer exists."""
    mapped = node.device.points if node.device is not None else {}
    values: dict[SldRole, SldValue | None] = {}
    for role in SLD_ROLES_BY_NODE_TYPE.get(node.type, ()):
        reading = readings_by_point.get(mapped[role]) if role in mapped else None
        values[role] = sld_value(role, reading) if reading is not None else None
    return values
