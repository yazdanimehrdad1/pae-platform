"""UserDataService: a logged-in user's preferences, saved trends and notes.

The routers pass the user's id from the session, never one from the request, so a user only
ever reaches their own rows; an id that isn't theirs is a 404 like one that doesn't exist. The
bounds here keep one account's data small (the UI has tighter limits of its own).
"""

import asyncio
import json
from collections.abc import Callable
from datetime import datetime

from intelli_gateway.interfaces.user_data_store import UserDataStore
from intelli_gateway.schemas.tools import JSONValue
from intelli_gateway.schemas.user_data import (
    MAX_NOTES,
    MAX_PREFERENCE_BYTES,
    MAX_PREFERENCES,
    MAX_TRENDS,
    Note,
    Preference,
    SavedTrend,
    TrendDefinition,
)
from intelli_gateway.utils.exceptions import InvalidRequestError, NotFoundError


class UserDataService:
    def __init__(self, store: UserDataStore, clock: Callable[[], datetime]) -> None:
        self._store = store
        self._clock = clock
        # One lock per user around each check-then-write (limits, reorder, delete), so two
        # requests at once can't pass a limit together or collide on positions. Enough while the
        # gateway runs as one process (it does: one container per environment).
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    # --- preferences ---
    async def list_preferences(self, user_id: int) -> list[Preference]:
        return await self._store.list_preferences(user_id)

    async def get_preference(self, user_id: int, key: str) -> Preference:
        preference = await self._store.get_preference(user_id, key)
        if preference is None:
            raise NotFoundError(f"no preference '{key}'")
        return preference

    async def put_preference(self, user_id: int, key: str, value: JSONValue) -> Preference:
        if len(json.dumps(value, separators=(",", ":"))) > MAX_PREFERENCE_BYTES:
            raise InvalidRequestError(f"a preference value is at most {MAX_PREFERENCE_BYTES} bytes")
        async with self._lock(user_id):
            if await self._store.get_preference(user_id, key) is None:
                if len(await self._store.list_preferences(user_id)) >= MAX_PREFERENCES:
                    raise InvalidRequestError(f"at most {MAX_PREFERENCES} preferences per user")
            return await self._store.put_preference(user_id, key, value, self._clock())

    async def delete_preference(self, user_id: int, key: str) -> None:
        if not await self._store.delete_preference(user_id, key):
            raise NotFoundError(f"no preference '{key}'")

    # --- saved trends ---
    async def list_trends(self, user_id: int) -> list[SavedTrend]:
        return await self._store.list_trends(user_id)

    async def create_trend(self, user_id: int, trend: TrendDefinition) -> SavedTrend:
        async with self._lock(user_id):
            if len(await self._store.list_trends(user_id)) >= MAX_TRENDS:
                raise InvalidRequestError(f"at most {MAX_TRENDS} saved trends per user")
            return await self._store.create_trend(user_id, trend, self._clock())

    async def update_trend(self, user_id: int, trend_id: int, trend: TrendDefinition) -> SavedTrend:
        saved = await self._store.update_trend(user_id, trend_id, trend, self._clock())
        if saved is None:
            raise NotFoundError(f"no trend {trend_id}")
        return saved

    async def delete_trend(self, user_id: int, trend_id: int) -> None:
        async with self._lock(user_id):
            deleted = await self._store.delete_trend(user_id, trend_id)
        if not deleted:
            raise NotFoundError(f"no trend {trend_id}")

    async def reorder_trends(self, user_id: int, trend_ids: list[int]) -> list[SavedTrend]:
        async with self._lock(user_id):
            owned = {trend.id for trend in await self._store.list_trends(user_id)}
            if len(trend_ids) != len(owned) or set(trend_ids) != owned:
                raise InvalidRequestError("the order must list each of your trends exactly once")
            await self._store.reorder_trends(user_id, trend_ids, self._clock())
            return await self._store.list_trends(user_id)

    # --- notes ---
    async def list_notes(self, user_id: int) -> list[Note]:
        return await self._store.list_notes(user_id)

    async def create_note(
        self,
        user_id: int,
        content: str,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> Note:
        """created_at / updated_at: kept from a note imported from the browser (never in the
        future); a new note gets now."""
        text = _content(content)
        async with self._lock(user_id):
            if len(await self._store.list_notes(user_id)) >= MAX_NOTES:
                raise InvalidRequestError(f"at most {MAX_NOTES} notes per user")
            now = self._clock()
            created = min(created_at or now, now)
            updated = min(max(updated_at or created, created), now)
            return await self._store.create_note(user_id, text, created, updated)

    async def update_note(self, user_id: int, note_id: int, content: str) -> Note:
        note = await self._store.update_note(user_id, note_id, _content(content), self._clock())
        if note is None:
            raise NotFoundError(f"no note {note_id}")
        return note

    async def delete_note(self, user_id: int, note_id: int) -> None:
        if not await self._store.delete_note(user_id, note_id):
            raise NotFoundError(f"no note {note_id}")


def _content(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        raise InvalidRequestError("a note can't be empty")
    return stripped
