"""The UserDataStore contract, shared by the in-memory fake (unit tests) and Postgres
(tests/integration): every implementation must pass these checks unchanged. Users 1 and 2 must
exist (the Postgres fixture creates them)."""

from datetime import UTC, datetime, timedelta

from intelli_gateway.interfaces.user_data_store import UserDataStore
from intelli_gateway.schemas.user_data import SeriesStyle, TrendDefinition

ANA, BOB = 1, 2
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)


def trend(name: str = "BESS", points: tuple[str, ...] = ("101", "102:3")) -> TrendDefinition:
    return TrendDefinition(
        name=name,
        points=list(points),
        scale="per-point",
        styles={"101": SeriesStyle(color="#ff0000", dash="dashed", width=3)},
    )


async def stores_any_json_preference(store: UserDataStore) -> None:
    value = {"siteId": "1001", "nested": [1, 2.5, None, True, "x"]}
    await store.put_preference(ANA, "live-data.config", value, NOW)
    await store.put_preference(ANA, "last-site", "1001", NOW)
    stored = await store.get_preference(ANA, "live-data.config")
    assert stored is not None and (stored.value, stored.updated_at) == (value, NOW)
    assert [pref.key for pref in await store.list_preferences(ANA)] == [
        "last-site",
        "live-data.config",
    ]


async def overwrites_and_deletes_a_preference(store: UserDataStore) -> None:
    await store.put_preference(ANA, "timezone-mode", "site", NOW)
    await store.put_preference(ANA, "timezone-mode", "mine", LATER)
    stored = await store.get_preference(ANA, "timezone-mode")
    assert stored is not None and (stored.value, stored.updated_at) == ("mine", LATER)
    assert await store.delete_preference(ANA, "timezone-mode")
    assert not await store.delete_preference(ANA, "timezone-mode")
    assert await store.get_preference(ANA, "timezone-mode") is None


async def saves_trends_in_order(store: UserDataStore) -> None:
    first = await store.create_trend(ANA, trend("First"), NOW)
    second = await store.create_trend(ANA, trend("Second", ()), NOW)
    assert (first.position, second.position) == (0, 1)
    assert (
        first.model_dump(include=set(TrendDefinition.model_fields)) == trend("First").model_dump()
    )
    assert (first.created_at, first.updated_at) == (NOW, NOW)
    assert [saved.name for saved in await store.list_trends(ANA)] == ["First", "Second"]


async def updates_a_trend(store: UserDataStore) -> None:
    saved = await store.create_trend(ANA, trend(), NOW)
    edited = TrendDefinition(name="Renamed", points=["7"], scale=None, styles=None)
    updated = await store.update_trend(ANA, saved.id, edited, LATER)
    assert updated is not None
    assert (updated.name, updated.points, updated.scale, updated.styles) == (
        "Renamed",
        ["7"],
        None,
        None,
    )
    assert (updated.position, updated.created_at, updated.updated_at) == (0, NOW, LATER)
    assert await store.list_trends(ANA) == [updated]
    restyled = TrendDefinition(name="Restyled", styles={"7": SeriesStyle(dash="dotted")})
    again = await store.update_trend(ANA, saved.id, restyled, LATER)
    assert again is not None and again.styles == {"7": SeriesStyle(dash="dotted")}
    assert again.styles is not None and isinstance(again.styles["7"], SeriesStyle)


async def deleting_a_trend_closes_the_gap(store: UserDataStore) -> None:
    ids = [(await store.create_trend(ANA, trend(name), NOW)).id for name in ("A", "B", "C")]
    assert await store.delete_trend(ANA, ids[0])
    assert not await store.delete_trend(ANA, ids[0])
    assert [(saved.name, saved.position) for saved in await store.list_trends(ANA)] == [
        ("B", 0),
        ("C", 1),
    ]


async def reorders_trends(store: UserDataStore) -> None:
    ids = [(await store.create_trend(ANA, trend(name), NOW)).id for name in ("A", "B", "C")]
    await store.reorder_trends(ANA, [ids[2], ids[0], ids[1]], LATER)
    assert [(saved.name, saved.position) for saved in await store.list_trends(ANA)] == [
        ("C", 0),
        ("A", 1),
        ("B", 2),
    ]


async def keeps_notes_newest_first(store: UserDataStore) -> None:
    old = await store.create_note(ANA, "old", NOW - timedelta(days=2), NOW - timedelta(days=2))
    new = await store.create_note(ANA, "new", NOW, NOW)
    assert [note.content for note in await store.list_notes(ANA)] == ["new", "old"]
    edited = await store.update_note(ANA, old.id, "old, edited", LATER)
    assert edited is not None and (edited.created_at, edited.updated_at) == (old.created_at, LATER)
    assert [note.id for note in await store.list_notes(ANA)] == [old.id, new.id]
    assert await store.delete_note(ANA, new.id)
    assert not await store.delete_note(ANA, new.id)
    assert [note.content for note in await store.list_notes(ANA)] == ["old, edited"]


async def one_user_never_reaches_anothers_data(store: UserDataStore) -> None:
    await store.put_preference(ANA, "last-site", "1001", NOW)
    ana_trend = await store.create_trend(ANA, trend("Ana's"), NOW)
    ana_note = await store.create_note(ANA, "Ana's note", NOW, NOW)
    bob_trend = await store.create_trend(BOB, trend("Bob's"), NOW)

    assert await store.list_preferences(BOB) == []
    assert await store.get_preference(BOB, "last-site") is None
    assert not await store.delete_preference(BOB, "last-site")
    assert [saved.name for saved in await store.list_trends(BOB)] == ["Bob's"]
    assert bob_trend.position == 0  # positions count per user
    assert await store.update_trend(BOB, ana_trend.id, trend("hijack"), LATER) is None
    assert not await store.delete_trend(BOB, ana_trend.id)
    assert await store.list_notes(BOB) == []
    assert await store.update_note(BOB, ana_note.id, "hijack", LATER) is None
    assert not await store.delete_note(BOB, ana_note.id)

    assert [saved.name for saved in await store.list_trends(ANA)] == ["Ana's"]
    assert [note.content for note in await store.list_notes(ANA)] == ["Ana's note"]
    assert await store.get_preference(ANA, "last-site") is not None


CHECKS = [
    stores_any_json_preference,
    overwrites_and_deletes_a_preference,
    saves_trends_in_order,
    updates_a_trend,
    deleting_a_trend_closes_the_gap,
    reorders_trends,
    keeps_notes_newest_first,
    one_user_never_reaches_anothers_data,
]
