"""Modbus live stream raw registers endpoint — streams register reads over SSE."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from helpers.live_stream_raw_registers import live_stream_raw_registers_generator
from helpers.live_stream_raw_registers.redis_history import LiveStreamHistoryStore
from schemas.api_models.live_stream_raw_registers import (
    LiveStreamDeleteAllSessionsResponse,
    LiveStreamDeleteSessionResponse,
    LiveStreamRawRegistersParams,
    LiveStreamSessionInfo,
    LiveStreamSessionsResponse,
    LiveStreamStopSessionResponse,
)
from services.server_sent_events import session_store

router = APIRouter(prefix="/modbus-live-stream-raw-registers", tags=["modbus-live-stream-raw-registers"])

_history_store = LiveStreamHistoryStore()


@router.post("/stream", response_class=StreamingResponse)
async def start_live_stream_raw_registers(params: LiveStreamRawRegistersParams):
    """
    Stream live Modbus raw register reads over Server-Sent Events.

    Connects to the target device, polls the specified register range at the given
    interval, and emits SSE events until duration expires or the client disconnects.

    Events:
    - connected: first event, contains session_id for use with the stop/delete endpoints
    - poll: one reading per interval with all register values
    - error: Modbus or connection error (stream continues unless unrecoverable)
    - done: emitted once when the session ends
    """
    return StreamingResponse(
        live_stream_raw_registers_generator(params),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions", response_model=LiveStreamSessionsResponse)
async def list_live_stream_sessions(
    status: Literal["active", "stopped"] | None = Query(None, description="Filter by status. Omit to return all.")
):
    """
    List sessions with their configs and status.

    - Omit `status` → all sessions with data in Redis (active + stopped within TTL)
    - `?status=active` → only currently polling sessions
    - `?status=stopped` → only sessions that have ended but whose data is still in Redis
    """
    active_ids = set(session_store.list_active())
    all_sessions = await _history_store.list_all_sessions()

    sessions = [
        LiveStreamSessionInfo(
            session_id=sid,
            status="active" if sid in active_ids else "stopped",
            host=p["host"],
            port=p["port"],
            server_address=p["server_address"],
            kind=p["kind"],
            start_address=p["start_address"],
            end_address=p["end_address"],
            interval=p["interval"],
            duration=p["duration"],
            modbus_address_mode=p["modbus_address_mode"],
        )
        for sid, p in all_sessions
    ]

    if status:
        sessions = [s for s in sessions if s.status == status]

    return LiveStreamSessionsResponse(sessions=sessions)


@router.get("/stream/{session_id}/resume", response_class=StreamingResponse)
async def resume_live_stream_raw_registers(session_id: str):
    """Resume a stopped session under the same session_id. History continues accumulating."""
    if session_id in set(session_store.list_active()):
        raise HTTPException(status_code=409, detail="Session is already active")
    raw = await _history_store.get_session_params(session_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Session not found or expired — start a new session")
    params = LiveStreamRawRegistersParams(**raw)
    cancel_event = session_store.resume(session_id)
    return StreamingResponse(
        live_stream_raw_registers_generator(
            params,
            existing_session_id=session_id,
            existing_cancel_event=cancel_event,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/stream/{session_id}/stop", status_code=200, response_model=LiveStreamStopSessionResponse)
async def stop_live_stream_raw_registers(session_id: str):
    """Stop polling. Redis data (session params + history) remains accessible until TTL expires."""
    if not session_store.cancel(session_id):
        raise HTTPException(status_code=404, detail="Session not found or already stopped")
    return LiveStreamStopSessionResponse(stopped=session_id)


@router.delete("/stream/{session_id}", status_code=200, response_model=LiveStreamDeleteSessionResponse)
async def delete_live_stream_raw_registers(session_id: str):
    """Stop polling and delete all Redis data for this session immediately."""
    session_store.cancel(session_id)  # no-op if already stopped/expired
    await _history_store.delete_session(session_id)
    return LiveStreamDeleteSessionResponse(deleted=session_id)


@router.delete("/sessions", status_code=200, response_model=LiveStreamDeleteAllSessionsResponse)
async def delete_all_live_stream_sessions():
    """Cancel all active sessions and delete all Redis data for every session."""
    cancelled_count = session_store.cancel_all()
    deleted_ids = await _history_store.delete_all_sessions()
    return LiveStreamDeleteAllSessionsResponse(
        cancelled_active_sessions=cancelled_count,
        deleted_count=len(deleted_ids),
        deleted_sessions=deleted_ids,
    )
