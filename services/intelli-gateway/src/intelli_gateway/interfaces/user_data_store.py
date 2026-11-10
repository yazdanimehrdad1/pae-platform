"""A user's stored preferences, saved trends and notes. Implementations: Postgres
(services/postgres/) and in memory (tests/doubles/user_data_store.py).

Every method takes the owning user's id and touches only that user's rows: another user's trend
or note id behaves exactly like one that doesn't exist (None / False), so ids leak nothing.
"""

from datetime import datetime
from typing import Protocol

from intelli_gateway.schemas.tools import JSONValue
from intelli_gateway.schemas.user_data import Note, Preference, SavedTrend, TrendDefinition


class UserDataStore(Protocol):
    # --- preferences ---
    async def list_preferences(self, user_id: int) -> list[Preference]:
        """Sorted by key."""
        ...

    async def get_preference(self, user_id: int, key: str) -> Preference | None: ...

    async def put_preference(
        self, user_id: int, key: str, value: JSONValue, at: datetime
    ) -> Preference: ...

    async def delete_preference(self, user_id: int, key: str) -> bool: ...

    # --- saved trends (in the user's order) ---
    async def list_trends(self, user_id: int) -> list[SavedTrend]: ...

    async def create_trend(self, user_id: int, trend: TrendDefinition, at: datetime) -> SavedTrend:
        """Appended after the user's last trend."""
        ...

    async def update_trend(
        self, user_id: int, trend_id: int, trend: TrendDefinition, at: datetime
    ) -> SavedTrend | None: ...

    async def delete_trend(self, user_id: int, trend_id: int) -> bool:
        """The trends after it move up, so positions stay 0..n-1."""
        ...

    async def reorder_trends(self, user_id: int, trend_ids: list[int], at: datetime) -> None:
        """trend_ids is exactly the user's trend ids, in the new order (the caller checks)."""
        ...

    # --- notes (most recently updated first) ---
    async def list_notes(self, user_id: int) -> list[Note]: ...

    async def create_note(
        self, user_id: int, content: str, created_at: datetime, updated_at: datetime
    ) -> Note: ...

    async def update_note(
        self, user_id: int, note_id: int, content: str, at: datetime
    ) -> Note | None: ...

    async def delete_note(self, user_id: int, note_id: int) -> bool: ...
