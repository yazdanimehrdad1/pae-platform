"""Passwords and the AuthService, on the in-memory store with a clock the test moves.

Invariant guarded: a password verifies only against its own scrypt hash; login fails with one
message for a wrong password, an unknown user and a disabled account; emails are
case-insensitive; the store keeps only the token's hash; a session slides forward on use (written
at most once a minute) and is refused once expired, after logout, after the user is disabled or
after a password change.
"""

from datetime import datetime, timedelta

import pytest
from fakes import FIXED_NOW

from intelli_gateway.auth.passwords import hash_password, verify_password
from intelli_gateway.auth.service import (
    INVALID_LOGIN,
    AuthService,
    SessionSettings,
    hash_token,
)
from intelli_gateway.fake_data.user_store import InMemoryUserStore
from intelli_gateway.utils.exceptions import (
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    UnauthorizedError,
)

PASSWORD = "correct horse battery"
TTL = timedelta(days=30)


class Clock:
    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store() -> InMemoryUserStore:
    return InMemoryUserStore()


@pytest.fixture
async def auth(store: InMemoryUserStore, clock: Clock) -> AuthService:
    service = AuthService(store, clock, SessionSettings(ttl=TTL))
    await service.create_user("Ana@Example.com", "Ana R", "engineer", PASSWORD)
    return service


class TestPasswords:
    def test_a_password_verifies_only_against_its_own_hash(self) -> None:
        stored = hash_password(PASSWORD)
        assert stored.startswith("scrypt$") and PASSWORD not in stored
        assert verify_password(PASSWORD, stored)
        assert not verify_password(PASSWORD + "x", stored)

    def test_each_hash_has_its_own_salt(self) -> None:
        assert hash_password(PASSWORD) != hash_password(PASSWORD)

    @pytest.mark.parametrize("stored", ["", "plain", "bcrypt$1$2$3$a$b", "scrypt$x$8$1$AA==$AA=="])
    def test_a_malformed_hash_never_matches(self, stored: str) -> None:
        assert not verify_password(PASSWORD, stored)


class TestUsers:
    async def test_emails_are_stored_lower_case_and_unique(self, auth: AuthService) -> None:
        with pytest.raises(ConflictError):
            await auth.create_user("ANA@EXAMPLE.COM", "Other", "monitor", PASSWORD)

    @pytest.mark.parametrize(
        "email", ["ana", "ana@", "@example.com", "ana @example.com", "ana@example"]
    )
    async def test_the_login_name_must_be_an_email_address(
        self, auth: AuthService, email: str
    ) -> None:
        with pytest.raises(InvalidRequestError, match="not an email address"):
            await auth.create_user(email, "Ana", "engineer", PASSWORD)

    async def test_a_short_password_is_refused(self, auth: AuthService) -> None:
        with pytest.raises(InvalidRequestError):
            await auth.create_user("bob@example.com", "Bob", "engineer", "short")

    async def test_managing_an_unknown_user_is_not_found(self, auth: AuthService) -> None:
        with pytest.raises(NotFoundError):
            await auth.set_disabled("nobody@example.com", True)


class TestLogin:
    async def test_login_returns_the_user_and_a_token_stored_only_as_its_hash(
        self, auth: AuthService, store: InMemoryUserStore, clock: Clock
    ) -> None:
        user, token = await auth.login("  Ana@Example.COM ", PASSWORD)
        assert (user.email, user.role, user.last_login_at) == (
            "ana@example.com",
            "engineer",
            clock.now,
        )
        assert await store.get_session(token) is None
        session = await store.get_session(hash_token(token))
        assert session is not None and session.expires_at == clock.now + TTL

    @pytest.mark.parametrize(
        ("email", "password"),
        [("ana@example.com", "wrong password"), ("bob@example.com", PASSWORD)],
    )
    async def test_wrong_password_and_unknown_user_fail_alike(
        self, auth: AuthService, email: str, password: str
    ) -> None:
        with pytest.raises(UnauthorizedError, match=INVALID_LOGIN):
            await auth.login(email, password)

    async def test_a_disabled_user_cannot_log_in(self, auth: AuthService) -> None:
        await auth.set_disabled("ana@example.com", True)
        with pytest.raises(UnauthorizedError, match=INVALID_LOGIN):
            await auth.login("ana@example.com", PASSWORD)

    async def test_each_login_is_its_own_session(self, auth: AuthService) -> None:
        _, first = await auth.login("ana@example.com", PASSWORD)
        _, second = await auth.login("ana@example.com", PASSWORD)
        assert first != second
        await auth.logout(first)
        assert (await auth.authenticate(second)).user.email == "ana@example.com"


class TestSessions:
    async def test_an_unknown_token_is_refused(self, auth: AuthService) -> None:
        with pytest.raises(UnauthorizedError):
            await auth.authenticate("made-up")

    async def test_use_slides_the_expiry_at_most_once_a_minute(
        self, auth: AuthService, store: InMemoryUserStore, clock: Clock
    ) -> None:
        _, token = await auth.login("ana@example.com", PASSWORD)
        clock.advance(timedelta(seconds=30))
        assert (await auth.authenticate(token)).renewed_until is None
        clock.advance(timedelta(seconds=31))
        renewed = await auth.authenticate(token)
        assert renewed.renewed_until == clock.now + TTL
        session = await store.get_session(hash_token(token))
        assert session is not None and session.last_seen_at == clock.now

    async def test_a_session_used_within_its_ttl_never_expires(
        self, auth: AuthService, clock: Clock
    ) -> None:
        _, token = await auth.login("ana@example.com", PASSWORD)
        for _ in range(3):
            clock.advance(TTL - timedelta(days=1))
            await auth.authenticate(token)

    async def test_an_expired_session_is_refused_and_removed(
        self, auth: AuthService, store: InMemoryUserStore, clock: Clock
    ) -> None:
        _, token = await auth.login("ana@example.com", PASSWORD)
        clock.advance(TTL)
        with pytest.raises(UnauthorizedError, match="expired"):
            await auth.authenticate(token)
        assert await store.get_session(hash_token(token)) is None

    async def test_logout_ends_the_session(self, auth: AuthService) -> None:
        _, token = await auth.login("ana@example.com", PASSWORD)
        await auth.logout(token)
        with pytest.raises(UnauthorizedError):
            await auth.authenticate(token)

    async def test_disabling_the_user_ends_their_sessions(self, auth: AuthService) -> None:
        _, token = await auth.login("ana@example.com", PASSWORD)
        await auth.set_disabled("ana@example.com", True)
        with pytest.raises(UnauthorizedError):
            await auth.authenticate(token)

    async def test_a_new_password_ends_the_sessions_and_replaces_the_old_one(
        self, auth: AuthService
    ) -> None:
        _, token = await auth.login("ana@example.com", PASSWORD)
        await auth.set_password("ana@example.com", "a brand new password")
        with pytest.raises(UnauthorizedError):
            await auth.authenticate(token)
        with pytest.raises(UnauthorizedError):
            await auth.login("ana@example.com", PASSWORD)
        user, _ = await auth.login("ana@example.com", "a brand new password")
        assert user.email == "ana@example.com"
