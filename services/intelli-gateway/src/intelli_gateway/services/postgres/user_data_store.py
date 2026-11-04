"""PostgresUserDataStore: preferences, saved trends and notes in this service's Postgres
(SQLAlchemy 2 Core over asyncpg). Tables from migration 004_user_data. Every statement is
filtered by user_id, so one user can never read or change another's rows."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    and_,
    case,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.schemas.tools import JSONValue
from intelli_gateway.schemas.user_data import Note, Preference, SavedTrend, TrendDefinition

metadata = MetaData()
users_table = Table("users", metadata, Column("id", BigInteger(), primary_key=True))
preferences_table = Table(
    "user_preferences",
    metadata,
    Column("user_id", BigInteger(), ForeignKey("users.id"), primary_key=True),
    Column("key", Text(), primary_key=True),
    Column("value", JSONB(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
trends_table = Table(
    "user_saved_trends",
    metadata,
    Column("id", BigInteger(), primary_key=True, autoincrement=True),
    Column("user_id", BigInteger(), ForeignKey("users.id"), nullable=False),
    Column("position", Integer(), nullable=False),
    Column("name", Text(), nullable=False),
    Column("points", JSONB(), nullable=False),
    Column("scale", Text()),
    Column("styles", JSONB()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
notes_table = Table(
    "user_notes",
    metadata,
    Column("id", BigInteger(), primary_key=True, autoincrement=True),
    Column("user_id", BigInteger(), ForeignKey("users.id"), nullable=False),
    Column("content", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

_TREND_COLUMNS = [column for column in trends_table.c if column.name != "user_id"]
_NOTE_COLUMNS = [column for column in notes_table.c if column.name != "user_id"]


def _trend_values(trend: TrendDefinition) -> dict[str, object]:
    return trend.model_dump(mode="json")


def _trend(row: RowMapping) -> SavedTrend:
    return SavedTrend.model_validate(dict(row))


def _note(row: RowMapping) -> Note:
    return Note.model_validate(dict(row))


def _preference(row: RowMapping) -> Preference:
    return Preference.model_validate(dict(row))


class PostgresUserDataStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    # --- preferences ---
    async def list_preferences(self, user_id: int) -> list[Preference]:
        query = (
            select(
                preferences_table.c.key, preferences_table.c.value, preferences_table.c.updated_at
            )
            .where(preferences_table.c.user_id == user_id)
            .order_by(preferences_table.c.key)
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(query)
            return [_preference(row) for row in result.mappings()]

    async def get_preference(self, user_id: int, key: str) -> Preference | None:
        query = select(
            preferences_table.c.key, preferences_table.c.value, preferences_table.c.updated_at
        ).where(and_(preferences_table.c.user_id == user_id, preferences_table.c.key == key))
        async with self._engine.connect() as connection:
            row = (await connection.execute(query)).mappings().one_or_none()
        return _preference(row) if row is not None else None

    async def put_preference(
        self, user_id: int, key: str, value: JSONValue, at: datetime
    ) -> Preference:
        statement = pg_insert(preferences_table).values(
            user_id=user_id, key=key, value=value, updated_at=at
        )
        statement = statement.on_conflict_do_update(
            index_elements=[preferences_table.c.user_id, preferences_table.c.key],
            set_={"value": statement.excluded.value, "updated_at": statement.excluded.updated_at},
        )
        async with self._engine.begin() as connection:
            await connection.execute(statement)
        return Preference(key=key, value=value, updated_at=at)

    async def delete_preference(self, user_id: int, key: str) -> bool:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                delete(preferences_table).where(
                    and_(preferences_table.c.user_id == user_id, preferences_table.c.key == key)
                )
            )
        return result.rowcount > 0

    # --- saved trends ---
    async def list_trends(self, user_id: int) -> list[SavedTrend]:
        query = (
            select(*_TREND_COLUMNS)
            .where(trends_table.c.user_id == user_id)
            .order_by(trends_table.c.position, trends_table.c.id)
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(query)
            return [_trend(row) for row in result.mappings()]

    async def create_trend(self, user_id: int, trend: TrendDefinition, at: datetime) -> SavedTrend:
        async with self._engine.begin() as connection:
            # Serialize concurrent appends for this user (the row lock on their account).
            await connection.execute(
                select(users_table.c.id).where(users_table.c.id == user_id).with_for_update()
            )
            next_position = (
                await connection.execute(
                    select(func.coalesce(func.max(trends_table.c.position) + 1, 0)).where(
                        trends_table.c.user_id == user_id
                    )
                )
            ).scalar_one()
            result = await connection.execute(
                insert(trends_table)
                .values(
                    user_id=user_id,
                    position=next_position,
                    created_at=at,
                    updated_at=at,
                    **_trend_values(trend),
                )
                .returning(*_TREND_COLUMNS)
            )
            return _trend(result.mappings().one())

    async def update_trend(
        self, user_id: int, trend_id: int, trend: TrendDefinition, at: datetime
    ) -> SavedTrend | None:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(trends_table)
                .where(and_(trends_table.c.user_id == user_id, trends_table.c.id == trend_id))
                .values(updated_at=at, **_trend_values(trend))
                .returning(*_TREND_COLUMNS)
            )
            row = result.mappings().one_or_none()
        return _trend(row) if row is not None else None

    async def delete_trend(self, user_id: int, trend_id: int) -> bool:
        async with self._engine.begin() as connection:
            deleted = (
                await connection.execute(
                    delete(trends_table)
                    .where(and_(trends_table.c.user_id == user_id, trends_table.c.id == trend_id))
                    .returning(trends_table.c.position)
                )
            ).scalar_one_or_none()
            if deleted is None:
                return False
            await connection.execute(
                update(trends_table)
                .where(and_(trends_table.c.user_id == user_id, trends_table.c.position > deleted))
                .values(position=trends_table.c.position - 1)
            )
        return True

    async def reorder_trends(self, user_id: int, trend_ids: list[int], at: datetime) -> None:
        if not trend_ids:
            return
        new_position = case(
            {trend_id: index for index, trend_id in enumerate(trend_ids)},
            value=trends_table.c.id,
        )
        async with self._engine.begin() as connection:
            await connection.execute(
                update(trends_table)
                .where(and_(trends_table.c.user_id == user_id, trends_table.c.id.in_(trend_ids)))
                .values(position=new_position, updated_at=at)
            )

    # --- notes ---
    async def list_notes(self, user_id: int) -> list[Note]:
        query = (
            select(*_NOTE_COLUMNS)
            .where(notes_table.c.user_id == user_id)
            .order_by(notes_table.c.updated_at.desc(), notes_table.c.id.desc())
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(query)
            return [_note(row) for row in result.mappings()]

    async def create_note(
        self, user_id: int, content: str, created_at: datetime, updated_at: datetime
    ) -> Note:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                insert(notes_table)
                .values(
                    user_id=user_id, content=content, created_at=created_at, updated_at=updated_at
                )
                .returning(*_NOTE_COLUMNS)
            )
            return _note(result.mappings().one())

    async def update_note(
        self, user_id: int, note_id: int, content: str, at: datetime
    ) -> Note | None:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(notes_table)
                .where(and_(notes_table.c.user_id == user_id, notes_table.c.id == note_id))
                .values(content=content, updated_at=at)
                .returning(*_NOTE_COLUMNS)
            )
            row = result.mappings().one_or_none()
        return _note(row) if row is not None else None

    async def delete_note(self, user_id: int, note_id: int) -> bool:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                delete(notes_table).where(
                    and_(notes_table.c.user_id == user_id, notes_table.c.id == note_id)
                )
            )
        return result.rowcount > 0
