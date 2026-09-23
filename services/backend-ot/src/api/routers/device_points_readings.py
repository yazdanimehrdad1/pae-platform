"""Device point readings endpoints — query timeseries by device_point_id."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from helpers.common.date_time import TimeRange, resolve_time_range
from helpers.reads.calculate_reads import translate_bitfield_to_named_map, translate_reading
from helpers.reads.device_points_readings import (
    get_latest_readings_by_point_ids,
    get_timeseries_by_point_ids,
)
from helpers.reads.query_params import (
    TZ_QUERY,
    in_display_tz,
    normalize_bound,
    parse_point_ids,
    resolve_display_tz,
)
from logger import get_logger
from schemas.api_models import (
    LatestMeta,
    LatestResponse,
    PointLatest,
    PointTimeseries,
    TimeseriesMeta,
    TimeseriesPoint,
    TimeseriesResponse,
)

router = APIRouter(prefix="/device-point-readings", tags=["device-point-readings"])
logger = get_logger(__name__)


# --- Endpoints ---

@router.get("/site/{site_id}/device/{device_id}/latest", response_model=LatestResponse, response_model_exclude_none=True)
async def get_latest_readings(
    site_id: int,
    device_id: int,
    point_ids: str | None = Query(None, description="Comma-separated device_point_ids (e.g. '1,2,3'). If omitted, returns all points for the device."),
    translate: bool = Query(False, description="Translate enum/bitfield values to human-readable form"),
    tz: str | None = TZ_QUERY,
):
    """Get the latest reading for each requested device point, keyed by device_point_id."""
    ids = parse_point_ids(point_ids)
    display_tz = resolve_display_tz(tz)

    try:
        rows = await get_latest_readings_by_point_ids(ids, site_id=site_id, device_id=device_id)
    except Exception as e:
        logger.error("get_latest_readings failed site=%s device=%s point_ids=%s: %s", site_id, device_id, ids, e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve readings") from e

    readings = {
        str(row["device_point_id"]): PointLatest.model_validate({
            **row,
            "timestamp": in_display_tz(row["timestamp"], display_tz),
            "translated_value": translate_reading(
                row["derived_value"],
                row["bitfield_detail"],
                row["enum_detail"],
            ) if translate else None,
        })
        for row in rows
    }
    return LatestResponse(
        meta=LatestMeta(
            site_id=site_id,
            device_id=device_id,
            point_ids=ids or None,
            total_count=len(readings),
        ),
        readings=readings,
    )


@router.get("/timeseries/site/{site_id}/device/{device_id}", response_model=TimeseriesResponse, response_model_exclude_none=True)
async def get_timeseries_readings(
    site_id: int,
    device_id: int,
    point_ids: str | None = Query(None, description="Comma-separated device_point_ids (e.g. '1,2,3'). If omitted, returns all points for the device."),
    start_time: datetime | None = Query(None, description="Start time in ISO format. Must carry a UTC offset (e.g. '2025-01-18T08:00:00Z' or '2025-01-18T00:00:00-08:00') unless tz is supplied. Cannot be combined with time_range."),
    end_time: datetime | None = Query(None, description="End time in ISO format. Must carry a UTC offset unless tz is supplied. Cannot be combined with time_range."),
    time_range: TimeRange | None = Query(None, description="Relative time window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M. Cannot be combined with start_time/end_time."),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum readings per point, taking the most recent N (returned newest-first)"),
    translate: bool = Query(False, description="Translate enum/bitfield values to human-readable form"),
    tz: str | None = TZ_QUERY,
):
    """
    Get time-series readings for each requested device point, keyed by device_point_id.
    Each entry contains point metadata and a timeseries array sorted newest-first —
    the most recent reading is always the first element, for any limit or time window.

    Time window — pick one approach:
    - time_range: shorthand token (e.g. '1H', '1D', '1W') resolved relative to UTC now
    - start_time / end_time: ISO timestamps carrying a UTC offset
    - Neither: returns all stored readings up to limit

    Timezones: readings are stored in UTC and returned in UTC by default. A timestamp
    without an offset is rejected rather than guessed — pass tz=<IANA zone> to read
    naive bounds as local wall-clock time and render the response in that zone.
    """
    ids = parse_point_ids(point_ids)
    display_tz = resolve_display_tz(tz)

    if time_range and (start_time or end_time):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Use either time_range or start_time/end_time, not both",
        )

    start_time = normalize_bound(start_time, "start_time", display_tz)
    end_time = normalize_bound(end_time, "end_time", display_tz)

    if time_range:
        start_time, end_time = resolve_time_range(time_range)
        logger.info("time_range=%s resolved to start=%s end=%s", time_range, start_time.isoformat(), end_time.isoformat())
    if start_time and end_time and start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time must be before end_time",
        )

    try:
        rows = await get_timeseries_by_point_ids(
            ids, site_id=site_id, device_id=device_id,
            start_time=start_time, end_time=end_time, limit=limit,
        )
    except Exception as e:
        logger.error("get_timeseries_readings failed site=%s device=%s point_ids=%s: %s", site_id, device_id, ids, e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve timeseries") from e

    readings: dict[str, PointTimeseries] = {}
    for row in rows:
        key = str(row["device_point_id"])
        if key not in readings:
            extra: dict = {}
            if translate:
                extra["enum_map"] = row["enum_detail"] or None
                if row["bitfield_detail"]:
                    extra["bit_labels"] = list(
                        translate_bitfield_to_named_map(0.0, row["bitfield_detail"]).keys()
                    )
            readings[key] = PointTimeseries.model_validate({**row, **extra})
        readings[key].timeseries.append(TimeseriesPoint.model_validate({
            **row,
            "timestamp": in_display_tz(row["timestamp"], display_tz),
            "translated_value": translate_reading(
                row["derived_value"],
                row["bitfield_detail"],
                row["enum_detail"],
            ) if translate else None,
        }))
        readings[key].count += 1

    return TimeseriesResponse(
        meta=TimeseriesMeta(
            site_id=site_id,
            device_id=device_id,
            point_ids=ids or None,
            total_count=len(rows),
            start_time=in_display_tz(start_time, display_tz),
            end_time=in_display_tz(end_time, display_tz),
        ),
        readings=readings,
    )
