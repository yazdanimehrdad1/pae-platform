"""In-memory registry of active SSE live poll sessions."""

import asyncio
import uuid

_sessions: dict[str, asyncio.Event] = {}


def register() -> tuple[str, asyncio.Event]:
    """Create a new session entry and return (session_id, cancel_event)."""
    session_id = str(uuid.uuid4())
    cancel = asyncio.Event()
    _sessions[session_id] = cancel
    return session_id, cancel


def cancel(session_id: str) -> bool:
    """Signal a session to stop. Returns True if found, False if not found."""
    event = _sessions.get(session_id)
    if event is None:
        return False
    event.set()
    return True


def unregister(session_id: str) -> None:
    """Remove a session from the registry."""
    _sessions.pop(session_id, None)


def list_active() -> list[str]:
    """Return all currently active session IDs."""
    return list(_sessions.keys())


def resume(session_id: str) -> asyncio.Event:
    """Re-register an existing session_id with a fresh cancel event."""
    cancel = asyncio.Event()
    _sessions[session_id] = cancel
    return cancel


def cancel_all() -> int:
    """Cancel all active sessions. Returns the number of sessions cancelled."""
    for event in _sessions.values():
        event.set()
    count = len(_sessions)
    _sessions.clear()
    return count
