"""UserDataService rules on top of the store, on the in-memory store.

Invariant guarded: a missing or someone else's preference, trend or note is NotFound; values,
counts and note contents are bounded; a reorder must list each of the user's trends exactly once;
an imported note keeps its dates but never gets one in the future.
"""

import asyncio
from datetime import timedelta

import pytest
from fakes import FIXED_NOW, fixed_clock
from user_data_store_contract import ANA, BOB, trend

from intelli_gateway.fake_data.user_data_store import InMemoryUserDataStore
from intelli_gateway.schemas.user_data import MAX_PREFERENCE_BYTES, MAX_TRENDS, SavedTrend
from intelli_gateway.user_data.service import UserDataService
from intelli_gateway.utils.exceptions import InvalidRequestError, NotFoundError


@pytest.fixture
def data() -> UserDataService:
    return UserDataService(InMemoryUserDataStore(), fixed_clock)


class TestPreferences:
    async def test_a_missing_preference_is_not_found(self, data: UserDataService) -> None:
        with pytest.raises(NotFoundError):
            await data.get_preference(ANA, "last-site")
        with pytest.raises(NotFoundError):
            await data.delete_preference(ANA, "last-site")

    async def test_a_value_over_the_size_limit_is_refused(self, data: UserDataService) -> None:
        with pytest.raises(InvalidRequestError):
            await data.put_preference(ANA, "big", "x" * MAX_PREFERENCE_BYTES)

    async def test_put_returns_what_was_stored(self, data: UserDataService) -> None:
        stored = await data.put_preference(ANA, "timezone-mode", "mine")
        assert (stored.value, stored.updated_at) == ("mine", FIXED_NOW)
        assert await data.get_preference(ANA, "timezone-mode") == stored


class TestTrends:
    async def test_someone_elses_trend_is_not_found(self, data: UserDataService) -> None:
        saved = await data.create_trend(ANA, trend())
        with pytest.raises(NotFoundError):
            await data.update_trend(BOB, saved.id, trend("hijack"))
        with pytest.raises(NotFoundError):
            await data.delete_trend(BOB, saved.id)

    async def test_the_number_of_trends_is_bounded(self, data: UserDataService) -> None:
        for index in range(MAX_TRENDS):
            await data.create_trend(ANA, trend(f"T{index}"))
        with pytest.raises(InvalidRequestError):
            await data.create_trend(ANA, trend("one too many"))
        await data.create_trend(BOB, trend())  # per user

    @pytest.mark.parametrize(
        "order", [[0], [0, 0], [0, 1, 99]], ids=["missing", "twice", "foreign"]
    )
    async def test_a_reorder_must_list_each_trend_once(
        self, data: UserDataService, order: list[int]
    ) -> None:
        ids = [(await data.create_trend(ANA, trend(name))).id for name in ("A", "B")]
        with pytest.raises(InvalidRequestError):
            await data.reorder_trends(ANA, [ids[index] if index < 2 else index for index in order])

    async def test_reorder_returns_the_new_order(self, data: UserDataService) -> None:
        ids = [(await data.create_trend(ANA, trend(name))).id for name in ("A", "B")]
        reordered = await data.reorder_trends(ANA, ids[::-1])
        assert [saved.name for saved in reordered] == ["B", "A"]


class TestNotes:
    async def test_a_note_is_trimmed_and_cannot_be_blank(self, data: UserDataService) -> None:
        note = await data.create_note(ANA, "  check INV2 fans  ")
        assert (note.content, note.created_at, note.updated_at) == (
            "check INV2 fans",
            FIXED_NOW,
            FIXED_NOW,
        )
        with pytest.raises(InvalidRequestError):
            await data.update_note(ANA, note.id, "   ")

    async def test_an_imported_note_keeps_its_dates_but_none_in_the_future(
        self, data: UserDataService
    ) -> None:
        week_ago = FIXED_NOW - timedelta(days=7)
        kept = await data.create_note(ANA, "old", week_ago, week_ago + timedelta(days=1))
        assert (kept.created_at, kept.updated_at) == (week_ago, week_ago + timedelta(days=1))
        future = FIXED_NOW + timedelta(days=1)
        clamped = await data.create_note(ANA, "from a fast clock", future, future)
        assert (clamped.created_at, clamped.updated_at) == (FIXED_NOW, FIXED_NOW)
        backwards = await data.create_note(
            ANA, "updated before created", week_ago, week_ago - timedelta(days=1)
        )
        assert backwards.updated_at == week_ago

    async def test_someone_elses_note_is_not_found(self, data: UserDataService) -> None:
        note = await data.create_note(ANA, "mine")
        with pytest.raises(NotFoundError):
            await data.update_note(BOB, note.id, "hijack")
        with pytest.raises(NotFoundError):
            await data.delete_note(BOB, note.id)


class YieldingStore(InMemoryUserDataStore):
    """Yields to other tasks while counting, as a real database round trip does."""

    async def list_trends(self, user_id: int) -> list[SavedTrend]:
        await asyncio.sleep(0)
        return await super().list_trends(user_id)


class TestConcurrency:
    async def test_simultaneous_creates_never_pass_the_limit(self) -> None:
        data = UserDataService(YieldingStore(), fixed_clock)
        for index in range(MAX_TRENDS - 1):
            await data.create_trend(ANA, trend(f"T{index}"))
        results = await asyncio.gather(
            data.create_trend(ANA, trend("racer 1")),
            data.create_trend(ANA, trend("racer 2")),
            return_exceptions=True,
        )
        assert sum(isinstance(result, InvalidRequestError) for result in results) == 1
        assert len(await data.list_trends(ANA)) == MAX_TRENDS
