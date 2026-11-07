"""InMemoryUserDataStore: preferences, saved trends and notes in process memory, for tests and
for running without DATABASE_URL. It behaves like the Postgres store (the shared contract in
tests/user_data_store_contract.py)."""

from datetime import datetime

from intelli_gateway.schemas.tools import JSONValue
from intelli_gateway.schemas.user_data import Note, Preference, SavedTrend, TrendDefinition


class InMemoryUserDataStore:
    def __init__(self) -> None:
        self._preferences: dict[tuple[int, str], Preference] = {}
        # trend id -> (owner, trend)
        self._trends: dict[int, tuple[int, SavedTrend]] = {}
        self._notes: dict[int, tuple[int, Note]] = {}
        self._next_id = 1

    def _new_id(self) -> int:
        new_id = self._next_id
        self._next_id += 1
        return new_id

    # --- preferences ---
    async def list_preferences(self, user_id: int) -> list[Preference]:
        return sorted(
            (pref for (owner, _), pref in self._preferences.items() if owner == user_id),
            key=lambda pref: pref.key,
        )

    async def get_preference(self, user_id: int, key: str) -> Preference | None:
        return self._preferences.get((user_id, key))

    async def put_preference(
        self, user_id: int, key: str, value: JSONValue, at: datetime
    ) -> Preference:
        preference = Preference(key=key, value=value, updated_at=at)
        self._preferences[(user_id, key)] = preference
        return preference

    async def delete_preference(self, user_id: int, key: str) -> bool:
        return self._preferences.pop((user_id, key), None) is not None

    # --- saved trends ---
    def _owned_trends(self, user_id: int) -> list[SavedTrend]:
        return [trend for owner, trend in self._trends.values() if owner == user_id]

    async def list_trends(self, user_id: int) -> list[SavedTrend]:
        return sorted(self._owned_trends(user_id), key=lambda trend: (trend.position, trend.id))

    async def create_trend(self, user_id: int, trend: TrendDefinition, at: datetime) -> SavedTrend:
        position = max((owned.position for owned in self._owned_trends(user_id)), default=-1) + 1
        saved = SavedTrend(
            id=self._new_id(), position=position, created_at=at, updated_at=at, **trend.model_dump()
        )
        self._trends[saved.id] = (user_id, saved)
        return saved

    async def update_trend(
        self, user_id: int, trend_id: int, trend: TrendDefinition, at: datetime
    ) -> SavedTrend | None:
        owned = self._trends.get(trend_id)
        if owned is None or owned[0] != user_id:
            return None
        # Validated, not model_copy: the styles must become SeriesStyle models again.
        saved = SavedTrend.model_validate(
            {**owned[1].model_dump(), **trend.model_dump(), "updated_at": at}
        )
        self._trends[trend_id] = (user_id, saved)
        return saved

    async def delete_trend(self, user_id: int, trend_id: int) -> bool:
        owned = self._trends.get(trend_id)
        if owned is None or owned[0] != user_id:
            return False
        del self._trends[trend_id]
        for other in self._owned_trends(user_id):
            if other.position > owned[1].position:
                self._trends[other.id] = (
                    user_id,
                    other.model_copy(update={"position": other.position - 1}),
                )
        return True

    async def reorder_trends(self, user_id: int, trend_ids: list[int], at: datetime) -> None:
        for position, trend_id in enumerate(trend_ids):
            owner, trend = self._trends[trend_id]
            if owner == user_id:
                self._trends[trend_id] = (
                    user_id,
                    trend.model_copy(update={"position": position, "updated_at": at}),
                )

    # --- notes ---
    async def list_notes(self, user_id: int) -> list[Note]:
        notes = [note for owner, note in self._notes.values() if owner == user_id]
        return sorted(notes, key=lambda note: (note.updated_at, note.id), reverse=True)

    async def create_note(
        self, user_id: int, content: str, created_at: datetime, updated_at: datetime
    ) -> Note:
        note = Note(
            id=self._new_id(), content=content, created_at=created_at, updated_at=updated_at
        )
        self._notes[note.id] = (user_id, note)
        return note

    async def update_note(
        self, user_id: int, note_id: int, content: str, at: datetime
    ) -> Note | None:
        owned = self._notes.get(note_id)
        if owned is None or owned[0] != user_id:
            return None
        note = owned[1].model_copy(update={"content": content, "updated_at": at})
        self._notes[note_id] = (user_id, note)
        return note

    async def delete_note(self, user_id: int, note_id: int) -> bool:
        owned = self._notes.get(note_id)
        if owned is None or owned[0] != user_id:
            return False
        del self._notes[note_id]
        return True
