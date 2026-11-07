"""Account management over HTTP (admins), changing your own password, and the accounts an
environment's configuration creates at startup.

Invariant guarded: only admins reach /api/v1/users (others 403, no session 401); an admin can add
an account, rename it, change its role, disable it (its sessions end at once) and reset its
password (its sessions end), but can't demote or disable their own account; a user changes their
own password only with the current one, keeping this session and ending the others; the first
admin is created only while there are no users; the demo account follows its secret.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import pytest
from doubles.services import build_test_services
from fakes import ScriptedLLMClient, fixed_clock, make_settings
from pydantic import TypeAdapter

from intelli_gateway.app import create_app
from intelli_gateway.auth.bootstrap import ensure_configured_accounts
from intelli_gateway.schemas.api_models.responses import UserResponse
from intelli_gateway.utils.exceptions import ForbiddenError
from intelli_gateway.wiring import Services

PASSWORD = "correct horse battery"
NEW_PASSWORD = "a new password"
USERS = TypeAdapter(list[UserResponse])


@dataclass
class Setup:
    services: Services
    transport: httpx.ASGITransport

    @asynccontextmanager
    async def client(
        self, email: str | None = None, password: str = PASSWORD
    ) -> AsyncIterator[httpx.AsyncClient]:
        """A client of its own (its own cookie jar, like a browser), logged in when given a user."""
        async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as client:
            if email:
                response = await client.post(
                    "/api/v1/auth/login", json={"email": email, "password": password}
                )
                assert response.status_code == 200, response.text
            yield client


@pytest.fixture
async def setup() -> AsyncIterator[Setup]:
    settings = make_settings(ANTHROPIC_API_KEY="test-key")
    services = build_test_services(settings, llm=ScriptedLLMClient(), clock=fixed_clock)
    await services.auth.create_user("root@example.com", "Root", "admin", PASSWORD)
    await services.auth.create_user("ana@example.com", "Ana", "engineer", PASSWORD)
    yield Setup(services, httpx.ASGITransport(app=create_app(settings, services)))


async def user_id(setup: Setup, email: str) -> int:
    users = await setup.services.auth.list_users()
    return next(user.id for user in users if user.email == email)


def account(email: str, role: str = "monitor") -> dict[str, str]:
    return {"email": email, "display_name": "Bob S", "role": role, "password": "bob password"}


class TestAccess:
    async def test_only_admins_manage_accounts(self, setup: Setup) -> None:
        async with setup.client() as anonymous, setup.client("ana@example.com") as engineer:
            assert (await anonymous.get("/api/v1/users")).status_code == 401
            assert (await engineer.get("/api/v1/users")).status_code == 403
            assert (
                await engineer.post("/api/v1/users", json=account("bob@example.com"))
            ).status_code == 403
        async with setup.client("root@example.com") as admin:
            listed = USERS.validate_python((await admin.get("/api/v1/users")).json())
        assert [user.email for user in listed] == ["ana@example.com", "root@example.com"]


class TestManaging:
    async def test_an_admin_adds_an_account_that_can_log_in(self, setup: Setup) -> None:
        async with setup.client("root@example.com") as admin:
            created = await admin.post("/api/v1/users", json=account("Bob@Example.com"))
            assert created.status_code == 201
            assert UserResponse.model_validate(created.json()).email == "bob@example.com"
            assert (
                await admin.post("/api/v1/users", json=account("bob@example.com"))
            ).status_code == 409
        async with setup.client("bob@example.com", "bob password") as bob:
            assert (await bob.get("/api/v1/me")).json()["role"] == "monitor"

    async def test_rename_change_role_and_disable_ends_the_session(self, setup: Setup) -> None:
        ana_id = await user_id(setup, "ana@example.com")
        async with (
            setup.client("root@example.com") as admin,
            setup.client("ana@example.com") as ana,
        ):
            renamed = UserResponse.model_validate(
                (
                    await admin.patch(
                        f"/api/v1/users/{ana_id}", json={"display_name": "Ana R", "role": "admin"}
                    )
                ).json()
            )
            assert (renamed.display_name, renamed.role) == ("Ana R", "admin")
            assert (await ana.get("/api/v1/me")).status_code == 200

            disabled = await admin.patch(f"/api/v1/users/{ana_id}", json={"disabled": True})
            assert UserResponse.model_validate(disabled.json()).disabled
            assert (await ana.get("/api/v1/me")).status_code == 401
            missing = await admin.patch("/api/v1/users/999", json={"disabled": True})
            assert missing.status_code == 404

    async def test_an_admin_cannot_demote_or_disable_themselves(self, setup: Setup) -> None:
        root_id = await user_id(setup, "root@example.com")
        async with setup.client("root@example.com") as admin:
            for change in ({"role": "engineer"}, {"disabled": True}):
                response = await admin.patch(f"/api/v1/users/{root_id}", json=change)
                assert response.status_code == 422
            renamed = await admin.patch(f"/api/v1/users/{root_id}", json={"display_name": "Boss"})
            assert renamed.status_code == 200

    async def test_a_reset_password_ends_the_users_sessions(self, setup: Setup) -> None:
        ana_id = await user_id(setup, "ana@example.com")
        path = f"/api/v1/users/{ana_id}/password"
        async with (
            setup.client("root@example.com") as admin,
            setup.client("ana@example.com") as ana,
        ):
            assert (await admin.put(path, json={"password": NEW_PASSWORD})).status_code == 204
            assert (await ana.get("/api/v1/me")).status_code == 401
            assert (await admin.put(path, json={"password": "short"})).status_code == 422
        async with setup.client("ana@example.com", NEW_PASSWORD) as ana:
            assert (await ana.get("/api/v1/me")).status_code == 200


class TestOwnPassword:
    async def test_needs_the_current_password_and_keeps_only_this_session(
        self, setup: Setup
    ) -> None:
        async with (
            setup.client("ana@example.com") as this_browser,
            setup.client("ana@example.com") as other_browser,
        ):
            wrong = await this_browser.put(
                "/api/v1/me/password",
                json={"current_password": "nope", "new_password": NEW_PASSWORD},
            )
            assert wrong.status_code == 403
            changed = await this_browser.put(
                "/api/v1/me/password",
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            )
            assert changed.status_code == 204
            assert (await this_browser.get("/api/v1/me")).status_code == 200
            assert (await other_browser.get("/api/v1/me")).status_code == 401
        async with setup.client("ana@example.com", NEW_PASSWORD) as ana:
            assert (await ana.get("/api/v1/me")).status_code == 200


class TestSharedDemoAccount:
    async def test_nobody_changes_the_demo_password_from_inside_it(self, setup: Setup) -> None:
        await setup.services.auth.create_user("demo@plusdas.local", "Demo", "engineer", PASSWORD)
        async with setup.client("demo@plusdas.local") as demo:
            response = await demo.put(
                "/api/v1/me/password",
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            )
            assert response.status_code == 403
        async with setup.client("demo@plusdas.local") as demo:  # the old password still works
            assert (await demo.get("/api/v1/me")).status_code == 200


class TestConfiguredAccounts:
    async def test_the_first_admin_is_created_only_on_an_empty_install(self) -> None:
        settings = make_settings(BOOTSTRAP_ADMIN_PASSWORD="first admin password")
        services = build_test_services(settings, llm=ScriptedLLMClient(), clock=fixed_clock)
        await ensure_configured_accounts(services.auth, settings)
        users = await services.auth.list_users()
        assert [(user.email, user.role) for user in users] == [("admin@plusdas.local", "admin")]

        await services.auth.reset_password(users[0].id, "changed in the UI")
        await ensure_configured_accounts(services.auth, settings)  # every restart
        _, token = await services.auth.login("admin@plusdas.local", "changed in the UI")
        assert token

    async def test_no_password_no_admin(self) -> None:
        settings = make_settings()
        services = build_test_services(settings, llm=ScriptedLLMClient(), clock=fixed_clock)
        await ensure_configured_accounts(services.auth, settings)
        assert await services.auth.list_users() == []

    async def test_the_demo_account_follows_its_secret(self) -> None:
        settings = make_settings(DEMO_USER_PASSWORD="demo secret one")
        services = build_test_services(settings, llm=ScriptedLLMClient(), clock=fixed_clock)
        await ensure_configured_accounts(services.auth, settings)
        user, _ = await services.auth.login("demo@plusdas.local", "demo secret one")
        assert user.role == "engineer"

        rotated = make_settings(DEMO_USER_PASSWORD="demo secret two")
        await ensure_configured_accounts(services.auth, rotated)
        _, token = await services.auth.login("demo@plusdas.local", "demo secret two")
        assert token

    async def test_the_demo_address_is_configurable_and_stays_protected(self) -> None:
        settings = make_settings(
            DEMO_USER_PASSWORD="demo secret one", DEMO_USER_EMAIL="demo@plusdas.dev"
        )
        services = build_test_services(settings, llm=ScriptedLLMClient(), clock=fixed_clock)
        await ensure_configured_accounts(services.auth, settings)
        user, token = await services.auth.login("demo@plusdas.dev", "demo secret one")
        with pytest.raises(ForbiddenError):
            await services.auth.change_own_password(user.id, token, "demo secret one", NEW_PASSWORD)

    def test_an_empty_address_means_the_default(self) -> None:
        settings = make_settings(BOOTSTRAP_ADMIN_EMAIL="", DEMO_USER_EMAIL=" ")
        assert (settings.bootstrap_admin_email, settings.demo_user_email) == (
            "admin@plusdas.local",
            "demo@plusdas.local",
        )
