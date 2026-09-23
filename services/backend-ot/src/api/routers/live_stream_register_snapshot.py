"""Live stream register snapshot endpoint — returns last 5 decoded register reads for a session."""

from fastapi import APIRouter, HTTPException, Query

from helpers.live_stream_raw_registers.decode import build_registers
from helpers.live_stream_raw_registers.redis_history import LiveStreamHistoryStore
from schemas.api_models.live_stream_raw_registers import LiveStreamRawRegistersParams
from schemas.api_models.live_stream_register_snapshot import (
    LiveStreamRegisterSnapshotEntry,
    LiveStreamRegisterSnapshotResponse,
)

router = APIRouter(
    prefix="/modbus-live-stream-register-snapshot",
    tags=["modbus-live-stream-register-snapshot"],
)

_store = LiveStreamHistoryStore()


@router.get("/registers", response_model=LiveStreamRegisterSnapshotResponse)
async def get_live_stream_register_snapshot(session_id: str = Query(..., description="session_id from the connected SSE event")):
    """
    Return the last 5 decoded register reads for a live stream session.

    Snapshots are ordered newest-first. timestamps[j] corresponds to registers[i].values[j].
    Returns empty lists if no polls have been recorded yet.
    Returns 404 if the session is unknown or its data has expired (TTL elapsed).
    """
    raw_params = await _store.get_session_params(session_id)
    if raw_params is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    params = LiveStreamRawRegistersParams(**raw_params)
    history = await _store.get_history(session_id)

    if not history:
        return LiveStreamRegisterSnapshotResponse(timestamps=[], registers=[])

    decoded_snapshots = [build_registers(snap["values"], params) for snap in history]
    timestamps = [snap["timestamp"] for snap in history]
    addresses = sorted(int(a) for a in decoded_snapshots[0])

    registers = [
        LiveStreamRegisterSnapshotEntry(
            address=addr,
            values=[snap.get(str(addr)).value if snap.get(str(addr)) else None
                    for snap in decoded_snapshots],
            label=decoded_snapshots[0][str(addr)].label,
            data_type=decoded_snapshots[0][str(addr)].data_type,
        )
        for addr in addresses
    ]

    return LiveStreamRegisterSnapshotResponse(timestamps=timestamps, registers=registers)
