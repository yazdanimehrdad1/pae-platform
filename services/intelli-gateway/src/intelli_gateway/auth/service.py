"""AuthService: users, login and sessions. The API layer only moves the token between this service
and the cookie; nothing else here knows about HTTP.

- Login checks the password and creates a session: a random token for the cookie, only its
  SHA-256 in the store.
- Each authenticated request slides the expiry forward, writing at most once per touch interval.
- Logout deletes the session; disabling a user or changing their password deletes all of theirs,
  and a disabled user's leftover session is refused anyway.
"""

import asyncio
import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from intelli_gateway.auth.passwords import (
    DUMMY_HASH,
    MIN_PASSWORD_LENGTH,
    hash_password,
    verify_password,
)
from intelli_gateway.interfaces.user_store import UserStore
from intelli_gateway.schemas.users import (
    DEMO_EMAIL,
    EMAIL_MAX_LENGTH,
    EMAIL_PATTERN,
    NewUser,
    Role,
    StoredUser,
    User,
    UserSession,
)
from intelli_gateway.utils.exceptions import (
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
    UnauthorizedError,
)

INVALID_LOGIN = "wrong email or password"


@dataclass(frozen=True)
class SessionSettings:
    ttl: timedelta = timedelta(days=30)
    # last_seen_at / expires_at are written at most this often per session.
    touch_interval: timedelta = timedelta(minutes=1)


@dataclass(frozen=True)
class Authenticated:
    user: User
    # Set when this request slid the expiry forward: the cookie should be re-issued with it.
    renewed_until: datetime | None = None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _public(user: User) -> User:
    """The user without the password hash (a StoredUser narrowed to User)."""
    return User.model_validate(user.model_dump(include=set(User.model_fields)))


class AuthService:
    def __init__(
        self,
        store: UserStore,
        clock: Callable[[], datetime],
        settings: SessionSettings | None = None,
        demo_email: str = DEMO_EMAIL,
    ) -> None:
        self._store = store
        self._clock = clock
        self._settings = settings or SessionSettings()
        # The shared demo account: its password can't be changed from inside it.
        self._demo_email = normalize_email(demo_email)

    @property
    def session_ttl(self) -> timedelta:
        return self._settings.ttl

    async def create_user(self, email: str, display_name: str, role: Role, password: str) -> User:
        _check_email(normalize_email(email))
        _check_password(password)
        password_hash = await asyncio.to_thread(hash_password, password)
        user = await self._store.create_user(
            NewUser(
                email=normalize_email(email),
                display_name=display_name.strip(),
                role=role,
                password_hash=password_hash,
            ),
            created_at=self._clock(),
        )
        return _public(user)

    async def set_disabled(self, email: str, disabled: bool) -> User:
        user = await self._require_user(email)
        await self._store.set_disabled(user.id, disabled)
        return _public(user.model_copy(update={"disabled": disabled}))

    async def set_password(self, email: str, password: str) -> User:
        _check_password(password)
        user = await self._require_user(email)
        await self._store.set_password_hash(
            user.id, await asyncio.to_thread(hash_password, password)
        )
        return _public(user)

    async def list_users(self) -> list[User]:
        return [_public(user) for user in await self._store.list_users()]

    async def update_user(
        self,
        actor: User,
        user_id: int,
        *,
        display_name: str | None = None,
        role: Role | None = None,
        disabled: bool | None = None,
    ) -> User:
        """An admin's change to an account. Admins can't demote or disable their own account,
        so there is always an admin left. Disabling ends the user's sessions."""
        user = await self._require_user_id(user_id)
        if user.id == actor.id and ((role is not None and role != user.role) or disabled):
            raise InvalidRequestError("you can't demote or disable your own account")
        if display_name is not None or role is not None:
            name = display_name.strip() if display_name is not None else user.display_name
            if not name:
                raise InvalidRequestError("the display name can't be empty")
            await self._store.update_user(user.id, name, role or user.role)
        if disabled is not None and disabled != user.disabled:
            await self._store.set_disabled(user.id, disabled)
        return _public(await self._require_user_id(user.id))

    async def reset_password(self, user_id: int, password: str) -> None:
        """An admin sets a user's password; every session of that user ends."""
        _check_password(password)
        user = await self._require_user_id(user_id)
        await self._store.set_password_hash(
            user.id, await asyncio.to_thread(hash_password, password)
        )

    async def change_own_password(
        self, user_id: int, token: str, current_password: str, new_password: str
    ) -> None:
        """The user's own change: needs the current password. Their other sessions end; this one
        (`token`) stays."""
        user = await self._require_user_id(user_id)
        if user.email == self._demo_email:
            raise ForbiddenError("the shared demo account's password can't be changed")
        if not await asyncio.to_thread(verify_password, current_password, user.password_hash):
            raise ForbiddenError("the current password is wrong")
        _check_password(new_password)
        await self._store.set_password_hash(
            user.id,
            await asyncio.to_thread(hash_password, new_password),
            keep_token_hash=hash_token(token),
        )

    async def ensure_bootstrap_admin(self, email: str, password: str) -> User | None:
        """A fresh install's first admin (from the environment's secret): created only while
        there are no users at all, so a later password change is never undone."""
        if await self._store.list_users():
            return None
        return await self.create_user(email, "Administrator", "admin", password)

    async def ensure_demo_user(self, email: str, password: str) -> bool:
        """Keeps the demo account in line with its secret: created if missing, its password
        reset if the secret changed (an admin may still disable it). True if anything changed."""
        user = await self._store.get_user_by_email(normalize_email(email))
        if user is None:
            await self.create_user(email, "Demo engineer", "engineer", password)
            return True
        if await asyncio.to_thread(verify_password, password, user.password_hash):
            return False
        await self.reset_password(user.id, password)
        return True

    async def login(self, email: str, password: str) -> tuple[User, str]:
        """The user and a new session token. Raises UnauthorizedError for a wrong email or
        password, or a disabled account (one message for all three)."""
        user = await self._store.get_user_by_email(normalize_email(email))
        matches = await asyncio.to_thread(
            verify_password, password, user.password_hash if user else DUMMY_HASH
        )
        if user is None or not matches or user.disabled:
            raise UnauthorizedError(INVALID_LOGIN)
        now = self._clock()
        token = secrets.token_urlsafe(32)
        await self._store.delete_expired_sessions(now)
        await self._store.create_session(
            UserSession(
                token_hash=hash_token(token),
                user_id=user.id,
                created_at=now,
                expires_at=now + self._settings.ttl,
                last_seen_at=now,
            )
        )
        await self._store.set_last_login(user.id, now)
        return _public(user.model_copy(update={"last_login_at": now})), token

    async def authenticate(self, token: str) -> Authenticated:
        """The session's user. Raises UnauthorizedError for an unknown, expired or revoked
        session, or a disabled user."""
        token_hash = hash_token(token)
        session = await self._store.get_session(token_hash)
        now = self._clock()
        if session is None:
            raise UnauthorizedError("not logged in")
        if session.expires_at <= now:
            await self._store.delete_session(token_hash)
            raise UnauthorizedError("session expired")
        user = await self._store.get_user(session.user_id)
        if user is None or user.disabled:
            await self._store.delete_session(token_hash)
            raise UnauthorizedError("not logged in")
        renewed_until = None
        if now - session.last_seen_at >= self._settings.touch_interval:
            renewed_until = now + self._settings.ttl
            await self._store.touch_session(token_hash, last_seen_at=now, expires_at=renewed_until)
        return Authenticated(user=_public(user), renewed_until=renewed_until)

    async def logout(self, token: str) -> None:
        await self._store.delete_session(hash_token(token))

    async def _require_user_id(self, user_id: int) -> StoredUser:
        user = await self._store.get_user(user_id)
        if user is None:
            raise NotFoundError(f"no user {user_id}")
        return user

    async def _require_user(self, email: str) -> User:
        user = await self._store.get_user_by_email(normalize_email(email))
        if user is None:
            raise NotFoundError(f"no user '{normalize_email(email)}'")
        return user


def _check_email(email: str) -> None:
    if len(email) > EMAIL_MAX_LENGTH or not re.fullmatch(EMAIL_PATTERN, email):
        raise InvalidRequestError(f"'{email}' is not an email address (name@domain.tld)")


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidRequestError(f"the password needs at least {MIN_PASSWORD_LENGTH} characters")
