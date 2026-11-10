"""Stored users and their login sessions. Implementations: Postgres (services/postgres/) and in
memory (tests/doubles/user_store.py). Emails are stored lower-case; callers pass them that way."""

from datetime import datetime
from typing import Protocol

from intelli_gateway.schemas.users import NewUser, Role, StoredUser, UserSession


class UserStore(Protocol):
    async def create_user(self, user: NewUser, created_at: datetime) -> StoredUser:
        """Raises ConflictError if the email is taken."""
        ...

    async def get_user(self, user_id: int) -> StoredUser | None: ...

    async def get_user_by_email(self, email: str) -> StoredUser | None: ...

    async def list_users(self) -> list[StoredUser]:
        """Sorted by email."""
        ...

    async def update_user(
        self, user_id: int, display_name: str, role: Role
    ) -> StoredUser | None: ...

    async def set_last_login(self, user_id: int, at: datetime) -> None: ...

    async def set_disabled(self, user_id: int, disabled: bool) -> None:
        """Disabling also deletes the user's sessions."""
        ...

    async def set_password_hash(
        self, user_id: int, password_hash: str, keep_token_hash: str | None = None
    ) -> None:
        """Also deletes the user's sessions (a new password logs every browser out), except
        `keep_token_hash`: the session of a user changing their own password."""
        ...

    async def create_session(self, session: UserSession) -> None: ...

    async def get_session(self, token_hash: str) -> UserSession | None: ...

    async def touch_session(
        self, token_hash: str, last_seen_at: datetime, expires_at: datetime
    ) -> None: ...

    async def delete_session(self, token_hash: str) -> None: ...

    async def delete_expired_sessions(self, now: datetime) -> int: ...
