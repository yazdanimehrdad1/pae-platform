"""Login, logout, /me and the session cookie over HTTP, in process, with the in-memory user store.

Invariant guarded: login sets an HttpOnly, SameSite=Lax, path-/ cookie holding the token (never
the body); /me answers 401 without a valid cookie and the user with one; logout clears the
cookie and the old token stops working; a slid session re-issues the cookie; with
AUTH_DEV_HEADERS off every /api/v1 route but login needs a session, and with it on a cookie
still takes precedence over the headers; /me never accepts the dev headers.
"""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import httpx
import pytest
from fakes import FIXED_NOW, ScriptedLLMClient, make_settings

from intelli_gateway.app import create_app
from intelli_gateway.schemas.api_models.responses import MeResponse
from intelli_gateway.wiring import Services, build_services

PASSWORD = "correct horse battery"
COOKIE = "plusdas_session"


class Clock:
    def __init__(self) -> None:
        self.now = FIXED_NOW

    def __call__(self) -> datetime:
        return self.now


async def make_client(dev_headers: bool, clock: Clock) -> tuple[httpx.AsyncClient, Services]:
    settings = make_settings(
        ANTHROPIC_API_KEY="test-key", AUTH_DEV_HEADERS=str(dev_headers).lower()
    )
    services = build_services(settings, llm=ScriptedLLMClient(), clock=clock)
    await services.auth.create_user("ana@example.com", "Ana R", "admin", PASSWORD)
    await services.auth.create_user("bob@example.com", "Bob S", "monitor", PASSWORD)
    app = create_app(settings, services)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return client, services


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def client(clock: Clock) -> AsyncIterator[httpx.AsyncClient]:
    client, _ = await make_client(dev_headers=False, clock=clock)
    async with client:
        yield client


async def login(client: httpx.AsyncClient, email: str = "ana@example.com") -> httpx.Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})


class TestLogin:
    async def test_login_sets_an_httponly_lax_cookie_and_returns_the_user(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await login(client)
        assert response.status_code == 200
        assert MeResponse.model_validate(response.json()) == MeResponse(
            id=1, email="ana@example.com", display_name="Ana R", role="admin"
        )
        set_cookie = response.headers["set-cookie"]
        assert set_cookie.startswith(f"{COOKIE}=")
        for attribute in ("HttpOnly", "Path=/", "SameSite=lax", "Max-Age=2592000"):
            assert attribute.lower() in set_cookie.lower()
        assert "secure" not in set_cookie.lower()
        assert response.cookies[COOKIE] not in response.text

    async def test_a_wrong_password_is_401_without_a_cookie(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": "ana@example.com", "password": "wrong password"}
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "wrong email or password"}
        assert "set-cookie" not in response.headers


class TestMe:
    async def test_me_without_a_cookie_is_401(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/v1/me")).status_code == 401

    async def test_me_with_a_made_up_cookie_is_401(self, client: httpx.AsyncClient) -> None:
        client.cookies.set(COOKIE, "made-up")
        assert (await client.get("/api/v1/me")).status_code == 401

    async def test_me_is_the_logged_in_user(self, client: httpx.AsyncClient) -> None:
        await login(client, "bob@example.com")
        response = await client.get("/api/v1/me")
        assert MeResponse.model_validate(response.json()).email == "bob@example.com"

    async def test_me_ignores_the_dev_headers(self, clock: Clock) -> None:
        client, _ = await make_client(dev_headers=True, clock=clock)
        async with client:
            response = await client.get("/api/v1/me", headers={"X-User-Id": "ana@example.com"})
        assert response.status_code == 401

    async def test_a_slid_session_reissues_the_cookie(
        self, client: httpx.AsyncClient, clock: Clock
    ) -> None:
        await login(client)
        clock.now += timedelta(seconds=30)
        assert "set-cookie" not in (await client.get("/api/v1/me")).headers
        clock.now += timedelta(minutes=1)
        assert (await client.get("/api/v1/me")).headers["set-cookie"].startswith(f"{COOKIE}=")

    async def test_an_expired_session_is_401(self, client: httpx.AsyncClient, clock: Clock) -> None:
        await login(client)
        clock.now += timedelta(days=31)
        assert (await client.get("/api/v1/me")).status_code == 401


class TestLogout:
    async def test_logout_clears_the_cookie_and_the_old_token_stops_working(
        self, client: httpx.AsyncClient
    ) -> None:
        token = (await login(client)).cookies[COOKIE]
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 204
        assert response.headers["set-cookie"].startswith(f'{COOKIE}=""')
        client.cookies.set(COOKIE, token)  # a copy kept somewhere else
        assert (await client.get("/api/v1/me")).status_code == 401

    async def test_logout_without_a_session_is_still_204(self, client: httpx.AsyncClient) -> None:
        assert (await client.post("/api/v1/auth/logout")).status_code == 204

    async def test_disabling_the_user_ends_the_session_at_once(self, clock: Clock) -> None:
        client, services = await make_client(dev_headers=False, clock=clock)
        async with client:
            await login(client)
            await services.auth.set_disabled("ana@example.com", True)
            assert (await client.get("/api/v1/me")).status_code == 401


class TestProtectedRoutes:
    @pytest.mark.parametrize("path", ["/api/v1/sites", "/api/v1/tools"])
    async def test_without_dev_headers_v1_routes_need_a_login(
        self, client: httpx.AsyncClient, path: str
    ) -> None:
        assert (await client.get(path, headers={"X-User-Id": "ana@example.com"})).status_code == 401
        await login(client)
        assert (await client.get(path)).status_code == 200

    async def test_health_stays_open(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/healthz")).status_code == 200

    async def test_with_dev_headers_a_cookie_still_takes_precedence(self, clock: Clock) -> None:
        client, _ = await make_client(dev_headers=True, clock=clock)
        async with client:
            assert (await client.get("/api/v1/sites")).status_code == 200  # the dev user
            client.cookies.set(COOKIE, "made-up")
            assert (await client.get("/api/v1/sites")).status_code == 401
