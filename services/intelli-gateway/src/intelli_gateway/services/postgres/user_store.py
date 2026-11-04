"""PostgresUserStore: users and login sessions in this service's Postgres (SQLAlchemy 2 Core over
asyncpg). Tables from migration 003_users."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Table,
    Text,
    and_,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.elements import ColumnElement

from intelli_gateway.schemas.users import NewUser, Role, StoredUser, UserSession
from intelli_gateway.utils.exceptions import ConflictError

metadata = MetaData()
users_table = Table(
    "users",
    metadata,
    Column("id", BigInteger(), primary_key=True, autoincrement=True),
    Column("email", Text(), nullable=False),
    Column("display_name", Text(), nullable=False),
    Column("password_hash", Text(), nullable=False),
    Column("role", Text(), nullable=False),
    Column("disabled", Boolean(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_login_at", DateTime(timezone=True)),
)
sessions_table = Table(
    "user_sessions",
    metadata,
    Column("token_hash", Text(), primary_key=True),
    Column("user_id", BigInteger(), ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
)


def _user(row: RowMapping) -> StoredUser:
    return StoredUser.model_validate(dict(row))


def _session(row: RowMapping) -> UserSession:
    return UserSession.model_validate(dict(row))


class PostgresUserStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create_user(self, user: NewUser, created_at: datetime) -> StoredUser:
        values = user.model_dump() | {"disabled": False, "created_at": created_at}
        try:
            async with self._engine.begin() as connection:
                result = await connection.execute(
                    insert(users_table).values(values).returning(*users_table.c)
                )
                return _user(result.mappings().one())
        except IntegrityError as error:
            raise ConflictError(f"email '{user.email}' is taken") from error

    async def get_user(self, user_id: int) -> StoredUser | None:
        return await self._one_user(users_table.c.id == user_id)

    async def get_user_by_email(self, email: str) -> StoredUser | None:
        return await self._one_user(users_table.c.email == email)

    async def list_users(self) -> list[StoredUser]:
        async with self._engine.connect() as connection:
            result = await connection.execute(select(users_table).order_by(users_table.c.email))
            return [_user(row) for row in result.mappings()]

    async def update_user(self, user_id: int, display_name: str, role: Role) -> StoredUser | None:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(users_table)
                .where(users_table.c.id == user_id)
                .values(display_name=display_name, role=role)
                .returning(*users_table.c)
            )
            row = result.mappings().one_or_none()
        return _user(row) if row is not None else None

    async def _one_user(self, condition: ColumnElement[bool]) -> StoredUser | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(select(users_table).where(condition))
            row = result.mappings().one_or_none()
        return _user(row) if row is not None else None

    async def set_last_login(self, user_id: int, at: datetime) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                update(users_table).where(users_table.c.id == user_id).values(last_login_at=at)
            )

    async def set_disabled(self, user_id: int, disabled: bool) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                update(users_table).where(users_table.c.id == user_id).values(disabled=disabled)
            )
            if disabled:
                await connection.execute(
                    delete(sessions_table).where(sessions_table.c.user_id == user_id)
                )

    async def set_password_hash(
        self, user_id: int, password_hash: str, keep_token_hash: str | None = None
    ) -> None:
        sessions = sessions_table.c.user_id == user_id
        if keep_token_hash is not None:
            sessions = and_(sessions, sessions_table.c.token_hash != keep_token_hash)
        async with self._engine.begin() as connection:
            await connection.execute(
                update(users_table)
                .where(users_table.c.id == user_id)
                .values(password_hash=password_hash)
            )
            await connection.execute(delete(sessions_table).where(sessions))

    async def create_session(self, session: UserSession) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(insert(sessions_table).values(session.model_dump()))

    async def get_session(self, token_hash: str) -> UserSession | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(sessions_table).where(sessions_table.c.token_hash == token_hash)
            )
            row = result.mappings().one_or_none()
        return _session(row) if row is not None else None

    async def touch_session(
        self, token_hash: str, last_seen_at: datetime, expires_at: datetime
    ) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                update(sessions_table)
                .where(sessions_table.c.token_hash == token_hash)
                .values(last_seen_at=last_seen_at, expires_at=expires_at)
            )

    async def delete_session(self, token_hash: str) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                delete(sessions_table).where(sessions_table.c.token_hash == token_hash)
            )

    async def delete_expired_sessions(self, now: datetime) -> int:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                delete(sessions_table).where(sessions_table.c.expires_at <= now)
            )
        return result.rowcount
