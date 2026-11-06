"""Export a device's NATIVE points as CSV, and import a CSV of them (helpers/device_points/points_csv.py
has the format and the rules).

An import is planned first (a dry run writes nothing). Applied, it runs in one transaction: rows
create points or replace every field of the point of that name (restoring a deleted one), and, if
asked, the device's NATIVE points missing from the file are soft-deleted. A file with any problem
applies nothing (ValidationError carrying every problem). Turning recording off on, or deleting, a
point that a standardized link, virtual point or user alarm reads is refused (ConflictError).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_async_session_factory
from helpers.device_points.device_points_crud import _recompute_scan_ranges
from helpers.device_points.points_csv import (
    CsvPoint,
    ImportPlan,
    parse_points_csv,
    plan_import,
    points_to_csv,
)
from helpers.device_points.recording_dependents import ensure_not_depended_on, recording_dependents
from schemas.api_models import PointsCsvChange, PointsCsvImportResult, PointsCsvProblem
from schemas.db_models.orm_models import DevicePoint
from utils.exceptions import ConflictError, ValidationError


async def _device_points(session: AsyncSession, device_id: int) -> list[DevicePoint]:
    result = await session.execute(select(DevicePoint).where(DevicePoint.device_id == device_id))
    return list(result.scalars().all())


async def export_points_csv(device_id: int) -> str:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        return points_to_csv(await _device_points(session, device_id))


def _result(plan: ImportPlan, *, applied: bool, deleted: list[str]) -> PointsCsvImportResult:
    return PointsCsvImportResult(
        applied=applied,
        created=[point.name for point in plan.created],
        updated=[PointsCsvChange(name=point.name, fields=fields) for point, fields in plan.updated],
        unchanged=[point.name for point in plan.unchanged],
        missing=plan.missing,
        deleted=deleted,
        errors=[
            PointsCsvProblem(line=problem.line, column=problem.column, message=problem.message)
            for problem in sorted(
                plan.problems, key=lambda item: (item.line or 0, item.column or "")
            )
        ],
    )


def _set_fields(point: DevicePoint, row: CsvPoint) -> None:
    point.poll_kind = row.poll_kind
    point.address = row.address
    point.size = row.size
    point.data_type = row.data_type
    point.scale_factor = row.scale_factor
    point.unit = row.unit
    point.byte_order = row.byte_order
    point.word_order = row.word_order
    point.point_class = row.point_class
    point.severity = row.severity
    point.enum_detail = row.enum_detail
    point.bitfield_detail = row.bitfield_detail


async def _ensure_deletable(session: AsyncSession, site_id: int, points: list[DevicePoint]) -> None:
    names_by_id = {point.id: point.name for point in points}
    dependents = await recording_dependents(session, site_id, names_by_id.keys())
    if dependents:
        details = "; ".join(
            f"'{names_by_id[point_id]}' is read by {', '.join(sorted(readers))}"
            for point_id, readers in sorted(dependents.items())
        )
        raise ConflictError(
            f"Can't delete points that other points or alarms read: {details}",
            payload={
                "dependents": {
                    str(point_id): sorted(readers) for point_id, readers in dependents.items()
                }
            },
        )


async def import_points_csv(
    site_id: int, device_id: int, text: str, *, dry_run: bool, delete_missing: bool
) -> PointsCsvImportResult:
    """Plan (dry_run) or apply a points CSV on the device. The caller checks the device exists."""
    rows, problems = parse_points_csv(text)
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        existing = await _device_points(session, device_id)
        plan = plan_import(rows, existing, delete_missing=delete_missing)
        plan.problems = problems + plan.problems
        if dry_run:
            return _result(plan, applied=False, deleted=[])
        if plan.problems:
            result = _result(plan, applied=False, deleted=[])
            raise ValidationError(
                f"The file has {len(result.errors)} problem(s); nothing was imported",
                payload={"errors": [error.model_dump() for error in result.errors]},
            )

        by_name = {point.name: point for point in existing}
        stopping: list[DevicePoint] = []
        for row, _fields in plan.updated:
            point = by_name[row.name]
            point.deleted_at = None
            if point.record_enabled and not row.record_enabled:
                stopping.append(point)
            point.record_enabled = row.record_enabled
            _set_fields(point, row)
        await ensure_not_depended_on(session, site_id, stopping)

        for row in plan.created:
            point = DevicePoint(
                site_id=site_id,
                device_id=device_id,
                name=row.name,
                category="NATIVE",
                record_enabled=row.record_enabled,
            )
            _set_fields(point, row)
            session.add(point)

        deleted: list[str] = []
        if delete_missing and plan.missing:
            doomed = [by_name[name] for name in plan.missing]
            await _ensure_deletable(session, site_id, doomed)
            now = datetime.now(UTC)
            for point in doomed:
                point.deleted_at = now
            deleted = plan.missing

        await session.flush()
        await _recompute_scan_ranges(session, device_id)
        await session.commit()
        return _result(plan, applied=True, deleted=deleted)
