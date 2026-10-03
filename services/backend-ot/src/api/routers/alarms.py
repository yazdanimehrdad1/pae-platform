"""System alarm endpoints: a site's alarm definitions (user and profile), the page snapshot and
the event history. Alarms are evaluated by the scheduler job 'alarm_evaluation', not here."""

from datetime import UTC, datetime
from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query, status

import db.sites as sites_db
from helpers.alarms.definitions import (
    create_user_alarm,
    delete_user_alarm,
    list_alarm_definitions,
    update_alarm,
)
from helpers.alarms.events import get_alarm_snapshot, query_alarm_events
from logger import get_logger
from schemas.api_models.alarms import (
    AlarmDefinitionCreateRequest,
    AlarmDefinitionResponse,
    AlarmDefinitionUpdateRequest,
    AlarmEventResponse,
    AlarmSeverity,
    AlarmSnapshotResponse,
)
from utils.exceptions import AppError, NotFoundError

router = APIRouter(prefix="/alarms", tags=["alarms"])
logger = get_logger(__name__)


def _alarm_error(e: Exception) -> NoReturn:
    """Map an exception to an HTTPException. Never returns."""
    if isinstance(e, AppError):
        detail = {"error": type(e).__name__, "message": e.message}
        if e.payload:
            detail.update(e.payload)
        raise HTTPException(status_code=e.http_status_code, detail=detail) from e
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal server error occurred"
    ) from e


@router.get(
    "/site/{site_id}/snapshot",
    response_model=AlarmSnapshotResponse,
    summary="The alarms page for now: alarms, active and recent events, recent log",
)
async def get_snapshot(site_id: int) -> AlarmSnapshotResponse:
    """The site's alarms (user and profile), active events plus those cleared within 6 h, and the
    raise/clear log of those 6 h. `now` is server time, so durations don't depend on a browser clock."""
    try:
        return await get_alarm_snapshot(site_id, datetime.now(UTC))
    except Exception as e:
        _alarm_error(e)


@router.get(
    "/site/{site_id}/events",
    response_model=list[AlarmEventResponse],
    summary="Alarm events over a time range (history)",
)
async def list_events(
    site_id: int,
    start_time: datetime = Query(..., description="Start (ISO, with a UTC offset)"),
    end_time: datetime = Query(..., description="End (ISO, with a UTC offset)"),
    device_id: int | None = Query(None),
    severity: AlarmSeverity | None = Query(None),
    definition_id: int | None = Query(None, description="One alarm's events"),
) -> list[AlarmEventResponse]:
    """Events that overlap [start_time, end_time]: raised before the end and cleared after the
    start, or still active. Newest raise first. A reversed range is 400 (the time-range middleware)."""
    if start_time.tzinfo is None or end_time.tzinfo is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="start_time and end_time need a UTC offset")
    try:
        if await sites_db.get_site_by_id(site_id) is None:
            raise NotFoundError(f"Site {site_id} not found")
        return await query_alarm_events(
            site_id, start_time, end_time, device_id=device_id, severity=severity, definition_id=definition_id
        )
    except Exception as e:
        _alarm_error(e)


@router.get(
    "/site/{site_id}/definitions",
    response_model=list[AlarmDefinitionResponse],
    summary="List a site's alarms (user and profile)",
)
async def list_definitions(
    site_id: int,
    include_deleted: bool = Query(False, description="Include deleted user alarms and retired profile alarms"),
) -> list[AlarmDefinitionResponse]:
    try:
        alarms = await list_alarm_definitions(site_id, include_deleted=include_deleted)
        return [AlarmDefinitionResponse.model_validate(alarm) for alarm in alarms]
    except Exception as e:
        _alarm_error(e)


@router.post(
    "/site/{site_id}/definitions",
    response_model=AlarmDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user alarm",
)
async def create_definition(site_id: int, body: AlarmDefinitionCreateRequest) -> AlarmDefinitionResponse:
    """
    A threshold (a point against a value or another point, or a bit test; with delay and
    deadband), a comms-stale check on a device, or a multi-point condition (ALL/ANY groups, with a
    delay). The points or device must be active on this site (400); the name is unique per site
    ignoring case (409); at most 20 alarms per site can be enabled (409). An enabled alarm is
    evaluated and shown in Active alarms.
    """
    try:
        return AlarmDefinitionResponse.model_validate(await create_user_alarm(site_id, body))
    except Exception as e:
        _alarm_error(e)


@router.put(
    "/site/{site_id}/definitions/{alarm_id}",
    response_model=AlarmDefinitionResponse,
    summary="Update an alarm",
)
async def update_definition(site_id: int, alarm_id: int, body: AlarmDefinitionUpdateRequest) -> AlarmDefinitionResponse:
    """
    Omitted fields keep their value. A profile alarm (defined in code) accepts only enabled,
    notify_mobile and notify_email (400 otherwise). Enabling more than 20 alarms on the site
    is 409. Disabling an alarm clears its active event. Changing a user alarm's rule (what it
    checks) clears its active event and restarts its delay; the new rule raises again on the next
    evaluation if it holds. Sending the same rule again changes nothing.
    """
    try:
        return AlarmDefinitionResponse.model_validate(await update_alarm(site_id, alarm_id, body))
    except Exception as e:
        _alarm_error(e)


@router.delete(
    "/site/{site_id}/definitions/{alarm_id}",
    response_model=AlarmDefinitionResponse,
    summary="Delete a user alarm",
)
async def delete_definition(site_id: int, alarm_id: int) -> AlarmDefinitionResponse:
    """Permanently delete a user alarm and all its alarm events (its history). Returns the alarm as
    it was. Profile alarms can't be deleted (400); disable them instead."""
    try:
        return await delete_user_alarm(site_id, alarm_id)
    except Exception as e:
        _alarm_error(e)
