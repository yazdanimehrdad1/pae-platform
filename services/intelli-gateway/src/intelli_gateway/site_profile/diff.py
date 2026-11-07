"""Compare an approved site profile with backend-ot's current catalog, and apply approved changes.

Pure functions: no I/O. Identity: a device by its device_id, a point by (device_id, its name
within the device). Qualified point names (`DEVICE.point`) follow the approved device name, so a
device rename is one device change, not a change on every point.
"""

from collections.abc import Collection, Iterable

from intelli_gateway.schemas.site_data import Device, PointInfo
from intelli_gateway.schemas.site_profile import (
    ChangeKind,
    ChangeTarget,
    ProfileChange,
    SiteCatalog,
)
from intelli_gateway.utils.exceptions import InvalidRequestError

PointKey = tuple[int, str]

SITE_FIELDS = ("name", "description", "capacity_kw", "timezone", "latitude", "longitude")
DEVICE_FIELDS = ("name", "type", "vendor", "model", "description")
# What a point means; its qualified name and equipment come from its device.
POINT_FIELDS = (
    "description",
    "unit",
    "data_type",
    "point_class",
    "severity",
    "enum_labels",
    "bit_labels",
)
SITE_CHANGE_ID = "site"
TOPOLOGY_CHANGE_ID = "topology"


def device_change_id(device_id: int) -> str:
    return f"device:{device_id}"


def point_change_id(key: PointKey) -> str:
    return f"point:{key[0]}:{key[1]}"


def local_point_name(point: PointInfo) -> str:
    """The point's name within its device (the qualified name without `DEVICE.`)."""
    return point.name.removeprefix(f"{point.device_name}.")


def point_key(point: PointInfo) -> PointKey:
    return (point.device_id, local_point_name(point))


def _differing(old: object, new: object, fields: Iterable[str]) -> tuple[str, ...]:
    return tuple(field for field in fields if getattr(old, field) != getattr(new, field))


def _points_by_device(points: Iterable[PointInfo]) -> dict[int, dict[str, PointInfo]]:
    grouped: dict[int, dict[str, PointInfo]] = {}
    for point in points:
        grouped.setdefault(point.device_id, {})[local_point_name(point)] = point
    return grouped


def _point_count(count: int) -> str:
    return f"{count} point" if count == 1 else f"{count} points"


def diff_catalogs(approved: SiteCatalog | None, current: SiteCatalog) -> list[ProfileChange]:
    """Every difference, in a stable order: site, devices, points, topology.
    With nothing approved yet, everything in the catalog is an addition."""
    changes: list[ProfileChange] = []
    if approved is None:
        changes.append(
            ProfileChange(
                change_id=SITE_CHANGE_ID,
                target=ChangeTarget.SITE,
                kind=ChangeKind.ADDED,
                summary=f"site '{current.site.name}'",
            )
        )
    else:
        fields = _differing(approved.site, current.site, SITE_FIELDS)
        if fields:
            changes.append(
                ProfileChange(
                    change_id=SITE_CHANGE_ID,
                    target=ChangeTarget.SITE,
                    kind=ChangeKind.CHANGED,
                    summary=f"site details changed: {', '.join(fields)}",
                    fields=fields,
                )
            )

    old_devices = {device.device_id: device for device in approved.devices} if approved else {}
    new_devices = {device.device_id: device for device in current.devices}
    old_points = _points_by_device(approved.points if approved else ())
    new_points = _points_by_device(current.points)

    for device_id in sorted(old_devices.keys() | new_devices.keys()):
        old, new = old_devices.get(device_id), new_devices.get(device_id)
        if old is None and new is not None:
            count = len(new_points.get(device_id, {}))
            changes.append(
                ProfileChange(
                    change_id=device_change_id(device_id),
                    target=ChangeTarget.DEVICE,
                    kind=ChangeKind.ADDED,
                    device_id=device_id,
                    summary=f"new {new.type} '{new.name}' with {_point_count(count)}",
                )
            )
        elif new is None and old is not None:
            changes.append(
                ProfileChange(
                    change_id=device_change_id(device_id),
                    target=ChangeTarget.DEVICE,
                    kind=ChangeKind.REMOVED,
                    device_id=device_id,
                    summary=f"{old.type} '{old.name}' removed",
                )
            )
        elif old is not None and new is not None:
            fields = _differing(old, new, DEVICE_FIELDS)
            if fields:
                renamed = f" (renamed to '{new.name}')" if "name" in fields else ""
                changes.append(
                    ProfileChange(
                        change_id=device_change_id(device_id),
                        target=ChangeTarget.DEVICE,
                        kind=ChangeKind.CHANGED,
                        device_id=device_id,
                        fields=fields,
                        summary=f"device '{old.name}' changed: {', '.join(fields)}{renamed}",
                    )
                )
            changes.extend(
                _point_changes(
                    old.name, old_points.get(device_id, {}), new_points.get(device_id, {})
                )
            )

    if approved is None or approved.topology != current.topology:
        changes.append(
            ProfileChange(
                change_id=TOPOLOGY_CHANGE_ID,
                target=ChangeTarget.TOPOLOGY,
                kind=ChangeKind.ADDED if approved is None else ChangeKind.CHANGED,
                summary=(
                    f"topology: {len(current.topology.nodes)} nodes, "
                    f"{len(current.topology.connections)} connections"
                ),
            )
        )
    return changes


def _point_changes(
    device_name: str, old_points: dict[str, PointInfo], new_points: dict[str, PointInfo]
) -> list[ProfileChange]:
    changes: list[ProfileChange] = []

    def point_change(
        device_id: int, name: str, kind: ChangeKind, summary: str, fields: tuple[str, ...] = ()
    ) -> ProfileChange:
        return ProfileChange(
            change_id=point_change_id((device_id, name)),
            target=ChangeTarget.POINT,
            kind=kind,
            device_id=device_id,
            point_name=name,
            fields=fields,
            summary=summary,
        )

    for name in sorted(old_points.keys() | new_points.keys()):
        old, new = old_points.get(name), new_points.get(name)
        qualified = f"{device_name}.{name}"
        if old is None and new is not None:
            changes.append(
                point_change(new.device_id, name, ChangeKind.ADDED, f"new point {qualified}")
            )
        elif new is None and old is not None:
            changes.append(
                point_change(old.device_id, name, ChangeKind.REMOVED, f"{qualified} removed")
            )
        elif old is not None and new is not None:
            fields = _differing(old, new, POINT_FIELDS)
            if fields:
                changes.append(
                    point_change(
                        old.device_id,
                        name,
                        ChangeKind.CHANGED,
                        f"{qualified} changed: {', '.join(fields)}",
                        fields,
                    )
                )
    return changes


def _named_for(point: PointInfo, device: Device) -> PointInfo:
    """The point as part of `device`: qualified name, device name and equipment follow it."""
    return point.model_copy(
        update={
            "name": f"{device.name}.{local_point_name(point)}",
            "device_name": device.name,
            "equipment": device.type.lower(),
        }
    )


def apply_changes(
    approved: SiteCatalog | None, current: SiteCatalog, change_ids: Collection[str]
) -> SiteCatalog:
    """The approved catalog with the chosen pending changes taken from `current`.

    Raises InvalidRequestError for an id that is not a pending change, and when onboarding (nothing
    approved yet) without approving the site itself."""
    pending = {change.change_id: change for change in diff_catalogs(approved, current)}
    unknown = sorted(set(change_ids) - pending.keys())
    if unknown:
        raise InvalidRequestError(f"not pending changes: {', '.join(unknown)}")
    if approved is None and SITE_CHANGE_ID not in change_ids:
        raise InvalidRequestError("a new site's first approval must include the 'site' change")

    site = current.site if SITE_CHANGE_ID in change_ids or approved is None else approved.site
    devices = {device.device_id: device for device in approved.devices} if approved else {}
    points = {point_key(point): point for point in approved.points} if approved else {}
    new_devices = {device.device_id: device for device in current.devices}
    new_points = {point_key(point): point for point in current.points}

    for change_id in change_ids:
        change = pending[change_id]
        if change.target is ChangeTarget.DEVICE and change.device_id is not None:
            device_id = change.device_id
            if change.kind is ChangeKind.REMOVED:
                devices.pop(device_id, None)
                points = {key: point for key, point in points.items() if key[0] != device_id}
            elif change.kind is ChangeKind.ADDED:
                devices[device_id] = new_devices[device_id]
                points.update(
                    {key: point for key, point in new_points.items() if key[0] == device_id}
                )
            else:
                devices[device_id] = new_devices[device_id]

    # Points after devices, so a point is named for its device as approved in this same step.
    for change_id in change_ids:
        change = pending[change_id]
        if change.target is not ChangeTarget.POINT or change.device_id is None:
            continue
        key = (change.device_id, change.point_name or "")
        if change.kind is ChangeKind.REMOVED:
            points.pop(key, None)
        else:
            points[key] = new_points[key]

    topology = (
        current.topology
        if TOPOLOGY_CHANGE_ID in change_ids or approved is None
        else approved.topology
    )
    return SiteCatalog(
        site=site,
        devices=tuple(devices[device_id] for device_id in sorted(devices)),
        points=tuple(
            sorted(
                (_named_for(point, devices[key[0]]) for key, point in points.items()),
                key=lambda point: point.name,
            )
        ),
        topology=topology,
    )


def points_with_pending_changes(approved: SiteCatalog, current: SiteCatalog) -> frozenset[str]:
    """Approved (qualified) point names whose definition changed in backend-ot and waits for
    approval: their live values are flagged, since their approved meaning may be out of date."""
    keys = {
        (change.device_id, change.point_name)
        for change in diff_catalogs(approved, current)
        if change.target is ChangeTarget.POINT and change.kind is ChangeKind.CHANGED
    }
    return frozenset(point.name for point in approved.points if point_key(point) in keys)
