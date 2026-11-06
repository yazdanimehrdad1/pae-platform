"""Device point management endpoints."""

from typing import Any, Literal, NoReturn

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from api.controllers.devices import get_device_by_id
from db.devices import lock_device_scan_ranges, reset_device_scan_ranges
from helpers.device_points import (
    bulk_upsert_device_points,
    clear_point_link,
    create_virtual_point,
    delete_device_points,
    get_deleted_device_points,
    get_device_points,
    restore_device_point,
    set_point_link,
    update_device_point,
    update_virtual_point,
)
from helpers.device_points.points_csv import template_csv
from helpers.device_points.points_csv_import import export_points_csv, import_points_csv
from logger import get_logger
from schemas.api_models import DevicePointResponse, PointClass, PointsCsvImportResult, Severity
from schemas.api_models.requests import (
    DevicePointsBulkRequest,
    DevicePointUpdateRequest,
    DeviceScanRanges,
    StandardizedPointLinkRequest,
    VirtualPointCreateRequest,
    VirtualPointUpdateRequest,
)
from utils.exceptions import AppError

router = APIRouter(
    prefix="/device-points",
    tags=["device-points"],
)
logger = get_logger(__name__)


def _point_error(e: Exception) -> NoReturn:
    """Map an exception to an HTTPException. Never returns."""
    if isinstance(e, AppError):
        detail = {"error": type(e).__name__, "message": e.message}
        if e.payload:
            detail.update(e.payload)
        raise HTTPException(status_code=e.http_status_code, detail=detail)
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal server error occurred",
    )


@router.get(
    "/site/{site_id}/device/{device_id}",
    response_model=list[DevicePointResponse],
    summary="List a device's points",
)
async def get_points_for_device(
    site_id: int,
    device_id: int,
    category: Literal["NATIVE", "STANDARDIZED", "VIRTUAL"] | None = Query(
        default=None,
        description="Filter points by category",
    ),
    include_deleted: bool = Query(default=False, description="Include soft-deleted points"),
    point_class: PointClass | None = Query(
        default=None,
        alias="class",
        description="Filter points by signal class: ANALOG, BINARY, ALARM or CONTROL",
    ),
    severity: Severity | None = Query(default=None, description="Filter points by severity: HIGH, MEDIUM or LOW"),
) -> list[DevicePointResponse]:
    """Get all registered points for a specific device."""
    try:
        await get_device_by_id(site_id, device_id)
        points = await get_device_points(
            device_id,
            category=category,
            include_deleted=include_deleted,
            point_class=point_class,
            severity=severity,
        )
        return [DevicePointResponse.model_validate(p, from_attributes=True) for p in points]
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.get(
    "/site/{site_id}/device/{device_id}/deleted",
    response_model=list[DevicePointResponse],
    summary="List a device's soft-deleted points",
)
async def get_deleted_points_for_device(
    site_id: int,
    device_id: int,
) -> list[DevicePointResponse]:
    """Get all soft-deleted points for a specific device, ordered by most recently deleted."""
    try:
        await get_device_by_id(site_id, device_id)
        points = await get_deleted_device_points(device_id)
        return [DevicePointResponse.model_validate(p, from_attributes=True) for p in points]
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


# --- Fixed-path PUT/DELETE routes MUST come before /{point_id} variants ---

@router.put(
    "/site/{site_id}/device/{device_id}/scan-ranges",
    response_model=DeviceScanRanges,
    summary="Override and lock a device's scan ranges",
)
async def override_scan_ranges(
    site_id: int,
    device_id: int,
    body: DeviceScanRanges,
) -> DeviceScanRanges:
    """Manually set scan ranges and lock them (auto-recompute disabled until reset)."""
    try:
        await get_device_by_id(site_id, device_id)
        await lock_device_scan_ranges(device_id, body)
        return body
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.delete(
    "/site/{site_id}/device/{device_id}/scan-ranges",
    response_model=DeviceScanRanges,
    summary="Reset a device's scan ranges to auto-computed",
)
async def reset_scan_ranges(
    site_id: int,
    device_id: int,
) -> DeviceScanRanges:
    """Clear the scan ranges lock and recompute from current NATIVE points."""
    try:
        await get_device_by_id(site_id, device_id)
        return await reset_device_scan_ranges(device_id)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.put(
    "/site/{site_id}/device/{device_id}/bulk",
    response_model=list[DevicePointResponse],
    summary="Bulk create/update a device's points",
)
async def bulk_upsert_points(
    site_id: int,
    device_id: int,
    body: DevicePointsBulkRequest,
) -> list[DevicePointResponse]:
    """
    Upsert multiple device points in one call.
    Points matched by name: existing names are updated, new names are created.
    Scan range recompute runs once at the end.
    record_enabled is changed on an existing point only when sent; turning it off is refused (409)
    while a standardized link, virtual point or user alarm reads the point.
    """
    try:
        await get_device_by_id(site_id, device_id)
        points = await bulk_upsert_device_points(site_id, device_id, body)
        return [DevicePointResponse.model_validate(p, from_attributes=True) for p in points]
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


CSV_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {"content": {"text/csv": {"schema": {"type": "string"}}}, "description": "The CSV file"}
}
MAX_CSV_BYTES = 1_000_000


def _csv_file(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/csv-template",
    response_class=Response,
    responses=CSV_RESPONSE,
    summary="An empty points CSV (the header row) to fill in and import",
)
async def points_csv_template() -> Response:
    """The columns of a device points CSV (NATIVE points only, so no Category), as on the device
    page's points table: Name, Poll Kind, Address and Data Type are required; Record, Size (the
    data type's), Unit, Scale, Byte Order, Word Order, Class, Severity and Enum / Bit Labels are
    optional."""
    return _csv_file(template_csv(), "device-points-template.csv")


@router.get(
    "/site/{site_id}/device/{device_id}/csv",
    response_class=Response,
    responses={**CSV_RESPONSE, 404: {"description": "No such device"}},
    summary="A device's NATIVE points as CSV",
)
async def export_points_csv_route(site_id: int, device_id: int) -> Response:
    """The device's active NATIVE points, one row each, in the format the import reads."""
    try:
        device = await get_device_by_id(site_id, device_id)
        content = await export_points_csv(device_id)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in device.name)
    return _csv_file(content, f"{safe_name}-points.csv")


@router.post(
    "/site/{site_id}/device/{device_id}/csv-import",
    response_model=PointsCsvImportResult,
    responses={
        400: {
            "description": "The file has problems (detail.errors lists them); nothing was imported"
        },
        404: {"description": "No such device"},
        409: {
            "description": "A point to delete or stop recording is read by another point or an alarm"
        },
        413: {"description": "The file is larger than 1 MB"},
    },
    summary="Import a device's NATIVE points from CSV (dry run by default)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"text/csv": {"schema": {"type": "string"}}},
        }
    },
)
async def import_points_csv_route(
    site_id: int,
    device_id: int,
    request: Request,
    dry_run: bool = Query(True, description="Only report what the import would do"),
    delete_missing: bool = Query(
        False, description="Soft-delete the device's NATIVE points that aren't in the file"
    ),
) -> PointsCsvImportResult:
    """Each row is a whole NATIVE point, matched by name: a new name creates a point, an existing
    one gets every field from the row (a blank optional cell clears it; a deleted point is
    restored). A dry run (the default) returns the plan and every problem of the file; with
    dry_run=false a file without problems is applied in one transaction (with delete_missing, the
    points not in the file go to the deleted points), and one with problems gets 400 and changes
    nothing. The format: GET /device-points/csv-template."""
    body = await request.body()
    if len(body) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": "PayloadTooLarge", "message": "The CSV is larger than 1 MB"},
        )
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": "The CSV isn't UTF-8 text"},
        ) from e
    try:
        await get_device_by_id(site_id, device_id)
        return await import_points_csv(
            site_id, device_id, text, dry_run=dry_run, delete_missing=delete_missing
        )
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.post(
    "/site/{site_id}/device/{device_id}/virtual",
    response_model=DevicePointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a virtual point",
)
async def create_virtual_point_for_device(
    site_id: int,
    device_id: int,
    body: VirtualPointCreateRequest,
) -> DevicePointResponse:
    """
    Create a VIRTUAL point computed on read from other points' stored readings (any device on the site):
    a condition (cases of ALL/ANY groups; the first match sets the state) or a calculation
    (sum/avg/min/max/difference/ratio × scale + offset). Inputs must be active, non-virtual
    points on this site; bit conditions need a bitfield input.
    """
    try:
        await get_device_by_id(site_id, device_id)
        point = await create_virtual_point(site_id, device_id, body)
        return DevicePointResponse.model_validate(point, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.put(
    "/site/{site_id}/device/{device_id}/virtual/{point_id}",
    response_model=DevicePointResponse,
    summary="Update a virtual point",
)
async def update_virtual_point_for_device(
    site_id: int,
    device_id: int,
    point_id: int,
    body: VirtualPointUpdateRequest,
) -> DevicePointResponse:
    """Update a VIRTUAL point's name, unit, class, severity or definition. Omitted fields are kept.
    A point the site profile owns (profile_point_key set) is changed in code only: 409.
    """
    try:
        await get_device_by_id(site_id, device_id)
        point = await update_virtual_point(site_id, device_id, point_id, body)
        return DevicePointResponse.model_validate(point, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.put(
    "/site/{site_id}/device/{device_id}/{point_id}/link",
    response_model=DevicePointResponse,
    summary="Link a standardized point to a real point",
)
async def link_standardized_point(
    site_id: int,
    device_id: int,
    point_id: int,
    body: StandardizedPointLinkRequest,
) -> DevicePointResponse:
    """
    Make a STANDARDIZED point show the readings of an active NATIVE point on the same device:
    reads return the source's stored readings x scale_factor, in unit. Replaces any existing link.
    Between power units the scale must convert them (W -> kW: 0.001), else 400.
    """
    try:
        await get_device_by_id(site_id, device_id)
        point = await set_point_link(site_id, device_id, point_id, body)
        return DevicePointResponse.model_validate(point, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.delete(
    "/site/{site_id}/device/{device_id}/{point_id}/link",
    response_model=DevicePointResponse,
    summary="Unlink a standardized point",
)
async def unlink_standardized_point(
    site_id: int,
    device_id: int,
    point_id: int,
) -> DevicePointResponse:
    """Unlink a STANDARDIZED point: it is an empty placeholder again (no source, unit or scale)."""
    try:
        await get_device_by_id(site_id, device_id)
        point = await clear_point_link(site_id, device_id, point_id)
        return DevicePointResponse.model_validate(point, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.put(
    "/site/{site_id}/device/{device_id}/{point_id}",
    response_model=DevicePointResponse,
    summary="Update a device point",
)
async def update_point(
    site_id: int,
    device_id: int,
    point_id: int,
    body: DevicePointUpdateRequest,
) -> DevicePointResponse:
    """Update a device point. Triggers scan range recompute unless locked.
    Turning record_enabled off is refused (409) while a standardized link, virtual point or user
    alarm reads the point.
    """
    try:
        await get_device_by_id(site_id, device_id)
        point = await update_device_point(point_id, body)
        return DevicePointResponse.model_validate(point, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.delete(
    "/site/{site_id}/device/{device_id}",
    response_model=list[DevicePointResponse],
    summary="Soft- or hard-delete device points",
)
async def delete_points(
    site_id: int,
    device_id: int,
    point_ids: list[int] = Query(..., description="Point IDs to delete, e.g. ?point_ids=1&point_ids=2"),
    mode: Literal["soft", "hard"] = Query(default="soft", description="soft=preserve readings, hard=cascade delete"),
    confirm: bool = Query(default=False, description="Required for mode=hard"),
) -> list[DevicePointResponse]:
    """Delete one or more device points. Returns the deleted points. Soft delete preserves readings; hard delete is permanent.
    Points the site profile owns (profile_point_key set) can't be deleted: 409.
    """
    try:
        if mode == "hard" and not confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ConfirmationRequired", "message": "Set confirm=true to permanently delete points and all their readings"},
            )
        await get_device_by_id(site_id, device_id)
        missing, deleted = await delete_device_points(device_id, point_ids, hard=(mode == "hard"))
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NotFoundError", "message": f"Points not found: {missing}"},
            )
        return [DevicePointResponse.model_validate(p, from_attributes=True) for p in deleted]
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)


@router.post(
    "/site/{site_id}/device/{device_id}/{point_id}/restore",
    response_model=DevicePointResponse,
    summary="Restore a soft-deleted device point",
)
async def restore_point(
    site_id: int,
    device_id: int,
    point_id: int,
) -> DevicePointResponse:
    """Restore a soft-deleted device point. Triggers scan range recompute."""
    try:
        await get_device_by_id(site_id, device_id)
        point = await restore_device_point(point_id)
        return DevicePointResponse.model_validate(point, from_attributes=True)
    except HTTPException:
        raise
    except Exception as e:
        _point_error(e)
