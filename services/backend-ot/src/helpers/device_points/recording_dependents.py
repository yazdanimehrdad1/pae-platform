"""What reads a point's stored readings, so it can't stop being recorded while something depends on it.

A NATIVE point with record_enabled = false gets no new readings. Everything computed from stored
readings then goes blank: a STANDARDIZED point linked to it (source_point_id), a VIRTUAL point that
reads it, and a USER alarm whose rule reads it. Turning recording off is refused (409) while any of
those exist; the reverse direction (pointing one of them at a non-recorded point) is refused by
check_input_points and apply_point_link.
"""

from collections.abc import Collection
from typing import assert_never

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.virtual_points.definition import condition_point_ids, referenced_point_ids
from schemas.api_models.alarms import CommsStaleAlarm, ConditionAlarm, ThresholdAlarm, UserAlarmRule
from schemas.db_models.orm_models import AlarmDefinition, DevicePoint
from utils.exceptions import ConflictError


def alarm_rule_point_ids(rule: UserAlarmRule) -> set[int]:
    """Every point a USER alarm rule reads (a comms_stale rule watches a device, not points)."""
    match rule:
        case ThresholdAlarm():
            point_ids: set[int] = condition_point_ids(rule.condition)
            return point_ids
        case ConditionAlarm():
            point_ids = condition_point_ids(rule.when)
            return point_ids
        case CommsStaleAlarm():
            return set()
        case _:
            assert_never(rule)


async def recording_dependents(
    session: AsyncSession, site_id: int, point_ids: Collection[int]
) -> dict[int, list[str]]:
    """For each of `point_ids` that something reads, what reads it (described for an error message)."""
    wanted = set(point_ids)
    dependents: dict[int, list[str]] = {}
    if not wanted:
        return dependents

    linked = await session.execute(
        select(DevicePoint).where(
            DevicePoint.category == "STANDARDIZED",
            DevicePoint.deleted_at.is_(None),
            DevicePoint.source_point_id.in_(wanted),
        )
    )
    for point in linked.scalars().all():
        if point.source_point_id is not None:
            dependents.setdefault(point.source_point_id, []).append(f"standardized point '{point.name}'")

    virtual = await session.execute(
        select(DevicePoint).where(
            DevicePoint.site_id == site_id,
            DevicePoint.category == "VIRTUAL",
            DevicePoint.deleted_at.is_(None),
        )
    )
    for point in virtual.scalars().all():
        if point.virtual_definition is None:
            continue
        for point_id in referenced_point_ids(point.virtual_definition) & wanted:
            dependents.setdefault(point_id, []).append(f"virtual point '{point.name}'")

    alarms = await session.execute(
        select(AlarmDefinition).where(AlarmDefinition.site_id == site_id, AlarmDefinition.source == "USER")
    )
    for alarm in alarms.scalars().all():
        if alarm.rule is None:
            continue
        for point_id in alarm_rule_point_ids(alarm.rule) & wanted:
            dependents.setdefault(point_id, []).append(f"alarm '{alarm.name}'")

    return dependents


async def ensure_not_depended_on(
    session: AsyncSession, site_id: int, points: Collection[DevicePoint]
) -> None:
    """ConflictError (409) if anything reads one of `points`, which are about to stop being recorded."""
    names_by_id = {point.id: point.name for point in points}
    dependents = await recording_dependents(session, site_id, names_by_id.keys())
    if not dependents:
        return
    details = "; ".join(
        f"'{names_by_id[point_id]}' is read by {', '.join(sorted(readers))}"
        for point_id, readers in sorted(dependents.items())
    )
    raise ConflictError(
        f"Can't stop recording points that other points or alarms read: {details}",
        payload={"dependents": {str(point_id): sorted(readers) for point_id, readers in dependents.items()}},
    )
