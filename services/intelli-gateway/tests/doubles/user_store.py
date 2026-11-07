"""InMemoryUserStore: users and sessions in process memory, for tests and for running without
DATABASE_URL (then accounts are lost on restart). Same behavior as the Postgres store."""

from datetime import datetime

from intelli_gateway.schemas.users import NewUser, Role, StoredUser, UserSession
from intelli_gateway.utils.exceptions import ConflictError


class InMemoryUserStore:
    def __init__(self) -> None:
        self._users: dict[int, StoredUser] = {}
        self._sessions: dict[str, UserSession] = {}

    async def create_user(self, user: NewUser, created_at: datetime) -> StoredUser:
        if any(existing.email == user.email for existing in self._users.values()):
            raise ConflictError(f"email '{user.email}' is taken")
        stored = StoredUser(
            id=len(self._users) + 1, disabled=False, created_at=created_at, **user.model_dump()
        )
        self._users[stored.id] = stored
        return stored

    async def get_user(self, user_id: int) -> StoredUser | None:
        return self._users.get(user_id)

    async def get_user_by_email(self, email: str) -> StoredUser | None:
        return next((user for user in self._users.values() if user.email == email), None)

    async def list_users(self) -> list[StoredUser]:
        return sorted(self._users.values(), key=lambda user: user.email)

    async def update_user(self, user_id: int, display_name: str, role: Role) -> StoredUser | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        updated = user.model_copy(update={"display_name": display_name, "role": role})
        self._users[user_id] = updated
        return updated

    async def set_last_login(self, user_id: int, at: datetime) -> None:
        self._users[user_id] = self._users[user_id].model_copy(update={"last_login_at": at})

    async def set_disabled(self, user_id: int, disabled: bool) -> None:
        self._users[user_id] = self._users[user_id].model_copy(update={"disabled": disabled})
        if disabled:
            self._delete_sessions_of(user_id)

    async def set_password_hash(
        self, user_id: int, password_hash: str, keep_token_hash: str | None = None
    ) -> None:
        self._users[user_id] = self._users[user_id].model_copy(
            update={"password_hash": password_hash}
        )
        self._delete_sessions_of(user_id, keep_token_hash)

    def _delete_sessions_of(self, user_id: int, keep_token_hash: str | None = None) -> None:
        self._sessions = {
            token_hash: session
            for token_hash, session in self._sessions.items()
            if session.user_id != user_id or token_hash == keep_token_hash
        }

    async def create_session(self, session: UserSession) -> None:
        self._sessions[session.token_hash] = session

    async def get_session(self, token_hash: str) -> UserSession | None:
        return self._sessions.get(token_hash)

    async def touch_session(
        self, token_hash: str, last_seen_at: datetime, expires_at: datetime
    ) -> None:
        session = self._sessions.get(token_hash)
        if session is not None:
            self._sessions[token_hash] = session.model_copy(
                update={"last_seen_at": last_seen_at, "expires_at": expires_at}
            )

    async def delete_session(self, token_hash: str) -> None:
        self._sessions.pop(token_hash, None)

    async def delete_expired_sessions(self, now: datetime) -> int:
        expired = [
            token_hash
            for token_hash, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for token_hash in expired:
            del self._sessions[token_hash]
        return len(expired)
