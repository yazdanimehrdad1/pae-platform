"""The ConversationStore contract, shared by the in-memory double (unit tests) and Postgres
(tests/integration): every implementation must pass these checks unchanged. Users 1 and 2 must
exist (the Postgres fixture creates them)."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from intelli_gateway.interfaces.conversation_store import ConversationStore
from intelli_gateway.schemas.agent import ChatMessage, Conversation
from intelli_gateway.schemas.conversations import NewTurn, StoredToolCall

ANA, BOB = 1, 2
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)


def conversation(
    conversation_id: str = "c1", user_id: int = ANA, site_id: int = 1, at: datetime = NOW
) -> Conversation:
    return Conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        site_id=site_id,
        title="INV2 state?",
        created_at=at,
        updated_at=at,
    )


def turn(question: str = "INV2 state?", at: datetime = NOW) -> NewTurn:
    return NewTurn(
        question=question,
        answer="INV2 is derated.",
        model="claude-test",
        stop_reason="end_turn",
        iterations=2,
        tool_calls=[
            StoredToolCall(
                name="get_point_values",
                args={"point_names": ["INV2.Status"], "nested": {"a": [1, 2.5, None]}},
                summary="INV2.Status = 3",
                duration_ms=12.5,
                is_error=False,
            )
        ],
        input_tokens=200,
        output_tokens=40,
        cache_read_input_tokens=1500,
        cache_creation_input_tokens=0,
        duration_ms=2345.6,
        created_at=at,
        site_local_time="2026-06-15T05:00:00-07:00",
    )


HISTORY: list[ChatMessage] = [
    {"role": "user", "content": [{"type": "text", "text": "INV2 state?"}]},
    {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "check", "signature": "sig"},
            {"type": "text", "text": "INV2 is derated."},
        ],
    },
]


async def keeps_the_history_and_numbers_the_turns(store: ConversationStore) -> None:
    first = conversation()
    first.messages = list(HISTORY)
    stored = await store.save(first, turn())
    assert (stored.position, stored.question, stored.feedback) == (0, "INV2 state?", None)
    assert stored.tool_calls == turn().tool_calls
    assert stored.created_at == NOW

    again = await store.get("c1")
    assert again is not None
    assert (again.user_id, again.site_id, again.title, again.messages) == (
        ANA,
        1,
        "INV2 state?",
        HISTORY,
    )
    again.messages = [*HISTORY, *HISTORY]
    again.updated_at = LATER
    second = await store.save(again, turn("and INV1?", LATER))
    assert second.position == 1 and second.turn_id != stored.turn_id

    reloaded = await store.get("c1")
    assert reloaded is not None
    assert (len(reloaded.messages), reloaded.created_at, reloaded.updated_at) == (4, NOW, LATER)
    assert [t.question for t in await store.turns("c1")] == ["INV2 state?", "and INV1?"]
    assert await store.get("missing") is None
    assert await store.turns("missing") == []


async def lists_a_users_conversations_newest_first(store: ConversationStore) -> None:
    await store.save(conversation("old", at=NOW), turn())
    await store.save(conversation("new", site_id=2, at=LATER), turn(at=LATER))
    await store.save(conversation("bobs", user_id=BOB, at=LATER), turn(at=LATER))
    old = await store.get("old")
    assert old is not None
    await store.save(old, turn("again"))

    mine = await store.list_for_user(ANA)
    assert [(s.conversation_id, s.site_id, s.turns) for s in mine] == [("new", 2, 1), ("old", 1, 2)]
    assert [s.conversation_id for s in await store.list_for_user(ANA, site_id=1)] == ["old"]
    assert [s.conversation_id for s in await store.list_for_user(BOB)] == ["bobs"]


async def sets_and_clears_feedback(store: ConversationStore) -> None:
    stored = await store.save(conversation(), turn())
    rated = await store.set_feedback("c1", stored.turn_id, "down", "wrong inverter", LATER)
    assert rated is not None
    assert (rated.feedback, rated.feedback_comment, rated.feedback_at) == (
        "down",
        "wrong inverter",
        LATER,
    )
    assert (await store.turns("c1"))[0].feedback == "down"
    cleared = await store.set_feedback("c1", stored.turn_id, None, "ignored", LATER)
    assert cleared is not None
    assert (cleared.feedback, cleared.feedback_comment, cleared.feedback_at) == (None, None, None)
    # A turn of another conversation, or none at all.
    await store.save(conversation("c2"), turn())
    assert await store.set_feedback("c2", stored.turn_id, "up", None, LATER) is None
    assert await store.set_feedback("c1", 999_999, "up", None, LATER) is None


CHECKS: list[Callable[[ConversationStore], Awaitable[None]]] = [
    keeps_the_history_and_numbers_the_turns,
    lists_a_users_conversations_newest_first,
    sets_and_clears_feedback,
]
