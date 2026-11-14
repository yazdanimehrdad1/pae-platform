"""PostgresConversationStore: AI conversations and their turns in this service's Postgres
(SQLAlchemy 2 Core over asyncpg). Tables from migration 008_conversations. A conversation is
kept until its user deletes it; its turns go with it (ON DELETE CASCADE)."""

from datetime import datetime
from typing import cast

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    and_,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from intelli_gateway.schemas.agent import ChatMessage, Conversation
from intelli_gateway.schemas.conversations import ConversationSummary, Feedback, NewTurn, Turn

metadata = MetaData()
users_table = Table("users", metadata, Column("id", BigInteger(), primary_key=True))
conversations_table = Table(
    "ai_conversations",
    metadata,
    Column("conversation_id", Text(), primary_key=True),
    Column("user_id", BigInteger(), ForeignKey("users.id"), nullable=False),
    Column("site_id", Integer(), nullable=False),
    Column("title", Text(), nullable=False),
    Column("messages", JSONB(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
turns_table = Table(
    "ai_turns",
    metadata,
    Column("turn_id", BigInteger(), primary_key=True, autoincrement=True),
    Column(
        "conversation_id",
        Text(),
        ForeignKey("ai_conversations.conversation_id"),
        nullable=False,
    ),
    Column("position", Integer(), nullable=False),
    Column("question", Text(), nullable=False),
    Column("answer", Text(), nullable=False),
    Column("model", Text()),
    Column("stop_reason", Text(), nullable=False),
    Column("iterations", Integer(), nullable=False),
    Column("tool_calls", JSONB(), nullable=False),
    Column("input_tokens", Integer(), nullable=False),
    Column("output_tokens", Integer(), nullable=False),
    Column("cache_read_input_tokens", Integer(), nullable=False),
    Column("cache_creation_input_tokens", Integer(), nullable=False),
    Column("duration_ms", Float(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("site_local_time", Text(), nullable=False),
    Column("feedback", Text()),
    Column("feedback_comment", Text()),
    Column("feedback_at", DateTime(timezone=True)),
)


def _conversation(row: RowMapping) -> Conversation:
    return Conversation(
        conversation_id=row["conversation_id"],
        user_id=row["user_id"],
        site_id=row["site_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        messages=cast(list[ChatMessage], row["messages"]),
    )


def _turn(row: RowMapping) -> Turn:
    return Turn.model_validate(dict(row))


async def _turn_row(connection: AsyncConnection, turn_id: int) -> Turn | None:
    query = select(turns_table).where(turns_table.c.turn_id == turn_id)
    row = (await connection.execute(query)).mappings().one_or_none()
    return _turn(row) if row is not None else None


# Each conversation's summary: its columns but the history, and how many turns it holds.
_TURN_COUNT = (
    select(func.count())
    .select_from(turns_table)
    .where(turns_table.c.conversation_id == conversations_table.c.conversation_id)
    .scalar_subquery()
)
SUMMARIES = select(
    conversations_table.c.conversation_id,
    conversations_table.c.site_id,
    conversations_table.c.title,
    conversations_table.c.created_at,
    conversations_table.c.updated_at,
    _TURN_COUNT.label("turns"),
)


class PostgresConversationStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get(self, conversation_id: str) -> Conversation | None:
        query = select(conversations_table).where(
            conversations_table.c.conversation_id == conversation_id
        )
        async with self._engine.connect() as connection:
            row = (await connection.execute(query)).mappings().one_or_none()
        return _conversation(row) if row is not None else None

    async def save(self, conversation: Conversation, turn: NewTurn) -> Turn:
        upsert = pg_insert(conversations_table).values(
            conversation_id=conversation.conversation_id,
            user_id=conversation.user_id,
            site_id=conversation.site_id,
            title=conversation.title,
            messages=conversation.messages,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        upsert = upsert.on_conflict_do_update(
            index_elements=[conversations_table.c.conversation_id],
            set_={
                "messages": upsert.excluded.messages,
                "updated_at": upsert.excluded.updated_at,
            },
        )
        async with self._engine.begin() as connection:
            await connection.execute(upsert)
            # The row lock on the conversation (taken by the upsert) serializes the numbering.
            position = (
                await connection.execute(
                    select(func.count())
                    .select_from(turns_table)
                    .where(turns_table.c.conversation_id == conversation.conversation_id)
                )
            ).scalar_one()
            inserted = await connection.execute(
                insert(turns_table)
                .values(
                    conversation_id=conversation.conversation_id,
                    position=position,
                    **turn.model_dump(mode="json", exclude={"created_at"}),
                    created_at=turn.created_at,
                )
                .returning(turns_table.c.turn_id)
            )
            turn_id = inserted.scalar_one()
            stored = await _turn_row(connection, turn_id)
        assert stored is not None
        return stored

    async def list_for_user(
        self, user_id: int, site_id: int | None = None
    ) -> list[ConversationSummary]:
        conditions = [conversations_table.c.user_id == user_id]
        if site_id is not None:
            conditions.append(conversations_table.c.site_id == site_id)
        query = SUMMARIES.where(and_(*conditions)).order_by(conversations_table.c.updated_at.desc())
        async with self._engine.connect() as connection:
            result = await connection.execute(query)
            return [ConversationSummary.model_validate(dict(row)) for row in result.mappings()]

    async def rename(self, conversation_id: str, title: str) -> ConversationSummary | None:
        this_one = conversations_table.c.conversation_id == conversation_id
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(conversations_table).where(this_one).values(title=title)
            )
            if result.rowcount == 0:
                return None
            row = (await connection.execute(SUMMARIES.where(this_one))).mappings().one()
            return ConversationSummary.model_validate(dict(row))

    async def delete(self, conversation_id: str) -> bool:
        statement = delete(conversations_table).where(
            conversations_table.c.conversation_id == conversation_id
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(statement)
            return result.rowcount > 0

    async def turns(self, conversation_id: str) -> list[Turn]:
        query = (
            select(turns_table)
            .where(turns_table.c.conversation_id == conversation_id)
            .order_by(turns_table.c.position)
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(query)
            return [_turn(row) for row in result.mappings()]

    async def set_feedback(
        self,
        conversation_id: str,
        turn_id: int,
        feedback: Feedback | None,
        comment: str | None,
        at: datetime,
    ) -> Turn | None:
        statement = (
            update(turns_table)
            .where(
                and_(
                    turns_table.c.turn_id == turn_id,
                    turns_table.c.conversation_id == conversation_id,
                )
            )
            .values(
                feedback=feedback,
                feedback_comment=comment if feedback is not None else None,
                feedback_at=at if feedback is not None else None,
            )
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(statement)
            if result.rowcount == 0:
                return None
            return await _turn_row(connection, turn_id)
