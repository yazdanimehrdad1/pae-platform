"""The UserStore contract, shared by the in-memory fake (unit tests) and Postgres
(tests/integration): every implementation must pass these checks unchanged."""

from datetime import UTC, datetime, timedelta

import pytest

from intelli_gateway.interfaces.user_store import UserStore
from intelli_gateway.schemas.users import NewUser, Role, UserSession
from intelli_gateway.utils.exceptions import ConflictError

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
TTL = timedelta(days=30)


def new_user(email: str = "ana@example.com", role: Role = "engineer") -> NewUser:
    return NewUser(email=email, display_name=email.title(), role=role, password_hash="scrypt$x")


def session(
    user_id: int, token_hash: str = "hash-1", expires_at: datetime = NOW + TTL
) -> UserSession:
    return UserSession(
        token_hash=token_hash,
        user_id=user_id,
        created_at=NOW,
        expires_at=expires_at,
        last_seen_at=NOW,
    )


async def creates_and_reads_users(store: UserStore) -> None:
    created = await store.create_user(new_user("ana@example.com", "admin"), created_at=NOW)
    assert (created.email, created.role, created.disabled) == ("ana@example.com", "admin", False)
    assert created.created_at == NOW and created.last_login_at is None
    assert await store.get_user(created.id) == created
    assert await store.get_user_by_email("ana@example.com") == created
    assert await store.get_user_by_email("bob@example.com") is None
    assert await store.get_user(created.id + 1000) is None


async def refuses_a_taken_email(store: UserStore) -> None:
    await store.create_user(new_user("ana@example.com"), created_at=NOW)
    with pytest.raises(ConflictError):
        await store.create_user(new_user("ana@example.com"), created_at=NOW)


async def records_the_last_login(store: UserStore) -> None:
    user = await store.create_user(new_user(), created_at=NOW)
    await store.set_last_login(user.id, NOW + timedelta(hours=1))
    stored = await store.get_user(user.id)
    assert stored is not None and stored.last_login_at == NOW + timedelta(hours=1)


async def stores_touches_and_deletes_sessions(store: UserStore) -> None:
    user = await store.create_user(new_user(), created_at=NOW)
    await store.create_session(session(user.id))
    assert await store.get_session("hash-1") == session(user.id)
    later = NOW + timedelta(minutes=5)
    await store.touch_session("hash-1", last_seen_at=later, expires_at=later + TTL)
    touched = await store.get_session("hash-1")
    assert touched is not None and (touched.last_seen_at, touched.expires_at) == (
        later,
        later + TTL,
    )
    await store.delete_session("hash-1")
    assert await store.get_session("hash-1") is None


async def disabling_a_user_ends_only_their_sessions(store: UserStore) -> None:
    ana = await store.create_user(new_user("ana@example.com"), created_at=NOW)
    bob = await store.create_user(new_user("bob@example.com"), created_at=NOW)
    await store.create_session(session(ana.id, "ana-1"))
    await store.create_session(session(ana.id, "ana-2"))
    await store.create_session(session(bob.id, "bob-1"))
    await store.set_disabled(ana.id, True)
    stored = await store.get_user(ana.id)
    assert stored is not None and stored.disabled
    assert await store.get_session("ana-1") is None and await store.get_session("ana-2") is None
    assert await store.get_session("bob-1") is not None
    await store.set_disabled(ana.id, False)
    enabled = await store.get_user(ana.id)
    assert enabled is not None and not enabled.disabled


async def a_new_password_ends_the_users_sessions(store: UserStore) -> None:
    user = await store.create_user(new_user(), created_at=NOW)
    await store.create_session(session(user.id))
    await store.set_password_hash(user.id, "scrypt$new")
    stored = await store.get_user(user.id)
    assert stored is not None and stored.password_hash == "scrypt$new"
    assert await store.get_session("hash-1") is None


async def deletes_expired_sessions(store: UserStore) -> None:
    user = await store.create_user(new_user(), created_at=NOW)
    await store.create_session(session(user.id, "expired", expires_at=NOW - timedelta(seconds=1)))
    await store.create_session(session(user.id, "live"))
    assert await store.delete_expired_sessions(NOW) == 1
    assert await store.get_session("expired") is None
    assert await store.get_session("live") is not None


async def lists_and_updates_users(store: UserStore) -> None:
    bob = await store.create_user(new_user("bob@example.com"), created_at=NOW)
    ana = await store.create_user(new_user("ana@example.com"), created_at=NOW)
    assert [user.email for user in await store.list_users()] == [
        "ana@example.com",
        "bob@example.com",
    ]
    updated = await store.update_user(bob.id, "Robert", "admin")
    assert updated is not None and (updated.display_name, updated.role) == ("Robert", "admin")
    assert await store.get_user(bob.id) == updated
    assert await store.update_user(ana.id + bob.id + 100, "x", "admin") is None


async def a_password_change_can_keep_one_session(store: UserStore) -> None:
    user = await store.create_user(new_user(), created_at=NOW)
    await store.create_session(session(user.id, "this-browser"))
    await store.create_session(session(user.id, "other-browser"))
    await store.set_password_hash(user.id, "scrypt$new", keep_token_hash="this-browser")
    assert await store.get_session("this-browser") is not None
    assert await store.get_session("other-browser") is None


CHECKS = [
    lists_and_updates_users,
    a_password_change_can_keep_one_session,
    creates_and_reads_users,
    refuses_a_taken_email,
    records_the_last_login,
    stores_touches_and_deletes_sessions,
    disabling_a_user_ends_only_their_sessions,
    a_new_password_ends_the_users_sessions,
    deletes_expired_sessions,
]
