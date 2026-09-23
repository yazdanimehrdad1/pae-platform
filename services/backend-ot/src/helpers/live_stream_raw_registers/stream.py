"""SSE generator for the modbus live stream raw registers feature."""

import asyncio
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from pydantic import BaseModel

from config import settings
from helpers.live_stream_raw_registers.decode import build_registers
from helpers.live_stream_raw_registers.redis_history import LiveStreamHistoryStore
from schemas.api_models.live_stream_raw_registers import (
    LiveStreamRawRegistersConnectedEvent,
    LiveStreamRawRegistersDoneEvent,
    LiveStreamRawRegistersErrorEvent,
    LiveStreamRawRegistersEvent,
    LiveStreamRawRegistersParams,
)
from services.server_sent_events import (
    LiveStreamRawRegistersConnection,
    LiveStreamRawRegistersConnectionError,
    session_store,
    translate_live_stream_raw_registers_error,
)

_history_store = LiveStreamHistoryStore()


def _sse(event: str, payload: BaseModel) -> str:
    return f"event: {event}\ndata: {payload.model_dump_json()}\n\n"


async def live_stream_raw_registers_generator(
    params: LiveStreamRawRegistersParams,
    *,
    existing_session_id: str | None = None,
    existing_cancel_event: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    if existing_session_id and existing_cancel_event:
        session_id, cancel_event = existing_session_id, existing_cancel_event
    else:
        session_id, cancel_event = session_store.register()
    try:
        await _history_store.store_session_params(session_id, params)
    except Exception:
        pass  # must not prevent the stream from starting
    yield _sse("connected", LiveStreamRawRegistersConnectedEvent(session_id=session_id))

    offset = -1 if params.modbus_address_mode == "one_based" else 0
    count = params.end_address - params.start_address + 1
    modbus_start = params.start_address + offset

    connection = LiveStreamRawRegistersConnection(
        host=params.host,
        port=params.port,
        timeout=settings.modbus_timeout_s,
    )
    deadline = time.monotonic() + params.duration
    poll_count = 0

    try:
        try:
            await connection.connect()
        except LiveStreamRawRegistersConnectionError as exc:
            yield _sse("error", LiveStreamRawRegistersErrorEvent(error=str(exc), poll=0))
            return

        while time.monotonic() < deadline and not cancel_event.is_set():
            t0 = time.monotonic()
            try:
                registers_raw = await connection.read(
                    kind=params.kind,
                    address=modbus_start,
                    count=count,
                    device_id=params.server_address,
                )
                poll_count += 1
                try:
                    await _history_store.push(
                        session_id=session_id,
                        timestamp=datetime.now(UTC).isoformat(),
                        values=registers_raw,
                    )
                except Exception:
                    pass  # history write must never kill the SSE stream
                registers = build_registers(registers_raw, params)
                yield _sse("poll", LiveStreamRawRegistersEvent(
                    timestamp=datetime.now(UTC),
                    poll=poll_count,
                    registers=registers,
                ))

            except Exception as exc:
                msg = translate_live_stream_raw_registers_error(exc, params.host, params.port)
                yield _sse("error", LiveStreamRawRegistersErrorEvent(error=msg, poll=poll_count))

            elapsed = time.monotonic() - t0
            remaining = max(0.0, params.interval - elapsed)
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=remaining)
                break  # cancel was set during sleep
            except TimeoutError:
                pass   # normal interval expiry

    finally:
        session_store.unregister(session_id)
        await connection.close()
        yield _sse("done", LiveStreamRawRegistersDoneEvent(total_polls=poll_count, duration_s=params.duration))
