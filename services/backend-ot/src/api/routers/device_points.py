"""Device point management endpoints."""

from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, Query, status

from api.controllers.devices import get_device_by_id
from db.devices import lock_device_scan_ranges, reset_device_scan_ranges
from helpers.device_points import (
    bulk_upsert_device_points,
    delete_device_points,
    get_deleted_device_points,
    get_device_points,
    restore_device_point,
    update_device_point,
)
from logger import get_logger
from schemas.api_models import DevicePointResponse
from schemas.api_models.requests import (
    DevicePointsBulkRequest,
    DevicePointUpdateRequest,
    DeviceScanRanges,
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
) -> list[DevicePointResponse]:
    """Get all registered points for a specific device."""
    try:
        await get_device_by_id(site_id, device_id)
        points = await get_device_points(device_id, category=category, include_deleted=include_deleted)
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
    """
    try:
        await get_device_by_id(site_id, device_id)
        points = await bulk_upsert_device_points(site_id, device_id, body)
        return [DevicePointResponse.model_validate(p, from_attributes=True) for p in points]
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
    """Update a device point. Triggers scan range recompute unless locked."""
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
    """Delete one or more device points. Returns the deleted points. Soft delete preserves readings; hard delete is permanent."""
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
