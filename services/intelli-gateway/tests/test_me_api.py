"""The /api/v1/me routes over HTTP, in process: two real logins, in-memory stores.

Invariant guarded: every /me route needs a session (never the dev headers, even when they are
on); a user's trends, notes and preferences round-trip; user B can neither see nor change
user A's data, and B's attempts are 404s that reveal nothing; the trend reorder route is not
mistaken for a trend id; bad keys and bodies are 422.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from doubles.services import build_test_services
from fakes import ScriptedLLMClient, fixed_clock, make_settings
from pydantic import TypeAdapter

from intelli_gateway.app import create_app
from intelli_gateway.schemas.user_data import Note, Preference, SavedTrend

PASSWORD = "correct horse battery"
TRENDS = TypeAdapter(list[SavedTrend])
NOTES = TypeAdapter(list[Note])
TREND = {
    "name": "BESS power",
    "points": ["101", "102:3", "fn:site:site-poi-active-power:0"],
    "scale": "per-point",
    "styles": {"101": {"color": "#ff0000", "dash": "dashed", "width": 3}},
}


@pytest.fixture
async def clients() -> AsyncIterator[tuple[httpx.AsyncClient, httpx.AsyncClient]]:
    """Ana and Bob, each logged in on their own client (their own cookie jar), on one app."""
    settings = make_settings(ANTHROPIC_API_KEY="test-key", AUTH_DEV_HEADERS="true")
    services = build_test_services(settings, llm=ScriptedLLMClient(), clock=fixed_clock)
    for name in ("ana@example.com", "bob@example.com"):
        await services.auth.create_user(name, name.title(), "engineer", PASSWORD)
    transport = httpx.ASGITransport(app=create_app(settings, services))
    ana = httpx.AsyncClient(transport=transport, base_url="http://test")
    bob = httpx.AsyncClient(transport=transport, base_url="http://test")
    async with ana, bob:
        for client, name in ((ana, "ana@example.com"), (bob, "bob@example.com")):
            response = await client.post(
                "/api/v1/auth/login", json={"email": name, "password": PASSWORD}
            )
            assert response.status_code == 200
        yield ana, bob


class TestNeedsALogin:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/v1/me/preferences"),
            ("PUT", "/api/v1/me/preferences/last-site"),
            ("GET", "/api/v1/me/trends"),
            ("POST", "/api/v1/me/trends"),
            ("PUT", "/api/v1/me/trends/order"),
            ("GET", "/api/v1/me/notes"),
            ("DELETE", "/api/v1/me/notes/1"),
        ],
    )
    async def test_without_a_session_every_me_route_is_401_even_with_dev_headers(
        self, clients: tuple[httpx.AsyncClient, httpx.AsyncClient], method: str, path: str
    ) -> None:
        ana, _ = clients
        ana.cookies.clear()
        response = await ana.request(method, path, json={}, headers={"X-User-Id": "1"})
        assert response.status_code == 401


class TestRoundTrip:
    async def test_trends_are_saved_edited_reordered_and_deleted(
        self, clients: tuple[httpx.AsyncClient, httpx.AsyncClient]
    ) -> None:
        ana, _ = clients
        created = await ana.post("/api/v1/me/trends", json=TREND)
        assert created.status_code == 201
        first = SavedTrend.model_validate(created.json())
        assert (first.name, first.points, first.position) == (TREND["name"], TREND["points"], 0)
        second = SavedTrend.model_validate(
            (await ana.post("/api/v1/me/trends", json={"name": "Empty"})).json()
        )
        assert (second.points, second.scale, second.styles) == ([], None, None)

        edited = await ana.put(f"/api/v1/me/trends/{first.id}", json={**TREND, "name": "Renamed"})
        assert SavedTrend.model_validate(edited.json()).name == "Renamed"

        reordered = await ana.put(
            "/api/v1/me/trends/order", json={"trend_ids": [second.id, first.id]}
        )
        assert [trend.name for trend in TRENDS.validate_python(reordered.json())] == [
            "Empty",
            "Renamed",
        ]

        assert (await ana.delete(f"/api/v1/me/trends/{second.id}")).status_code == 204
        listed = TRENDS.validate_python((await ana.get("/api/v1/me/trends")).json())
        assert [(trend.name, trend.position) for trend in listed] == [("Renamed", 0)]

    async def test_notes_round_trip(
        self, clients: tuple[httpx.AsyncClient, httpx.AsyncClient]
    ) -> None:
        ana, _ = clients
        note = Note.model_validate(
            (await ana.post("/api/v1/me/notes", json={"content": "check INV2"})).json()
        )
        edited = await ana.put(f"/api/v1/me/notes/{note.id}", json={"content": "INV2 fixed"})
        assert Note.model_validate(edited.json()).content == "INV2 fixed"
        assert [
            n.content for n in NOTES.validate_python((await ana.get("/api/v1/me/notes")).json())
        ] == ["INV2 fixed"]
        assert (await ana.delete(f"/api/v1/me/notes/{note.id}")).status_code == 204

    async def test_preferences_round_trip(
        self, clients: tuple[httpx.AsyncClient, httpx.AsyncClient]
    ) -> None:
        ana, _ = clients
        value = {"1001": {"alias": "BESS 1", "viewMode": "live"}}
        put = await ana.put("/api/v1/me/preferences/live-data.config", json={"value": value})
        assert Preference.model_validate(put.json()).value == value
        got = await ana.get("/api/v1/me/preferences/live-data.config")
        assert Preference.model_validate(got.json()).value == value
        assert (await ana.delete("/api/v1/me/preferences/live-data.config")).status_code == 204
        assert (await ana.get("/api/v1/me/preferences/live-data.config")).status_code == 404


class TestIsolation:
    async def test_bob_cannot_see_or_change_anas_data(
        self, clients: tuple[httpx.AsyncClient, httpx.AsyncClient]
    ) -> None:
        ana, bob = clients
        trend = SavedTrend.model_validate((await ana.post("/api/v1/me/trends", json=TREND)).json())
        note = Note.model_validate(
            (await ana.post("/api/v1/me/notes", json={"content": "Ana's"})).json()
        )
        await ana.put("/api/v1/me/preferences/last-site", json={"value": "1001"})

        assert (await bob.get("/api/v1/me/trends")).json() == []
        assert (await bob.get("/api/v1/me/notes")).json() == []
        assert (await bob.get("/api/v1/me/preferences")).json() == []
        assert (await bob.get("/api/v1/me/preferences/last-site")).status_code == 404
        hijacks = [
            await bob.put(f"/api/v1/me/trends/{trend.id}", json=TREND),
            await bob.delete(f"/api/v1/me/trends/{trend.id}"),
            await bob.put(f"/api/v1/me/notes/{note.id}", json={"content": "x"}),
            await bob.delete(f"/api/v1/me/notes/{note.id}"),
        ]
        assert [response.status_code for response in hijacks] == [404, 404, 404, 404]
        foreign_order = await bob.put("/api/v1/me/trends/order", json={"trend_ids": [trend.id]})
        assert foreign_order.status_code == 422

        assert [
            t.name for t in TRENDS.validate_python((await ana.get("/api/v1/me/trends")).json())
        ] == [TREND["name"]]
        assert [
            n.content for n in NOTES.validate_python((await ana.get("/api/v1/me/notes")).json())
        ] == ["Ana's"]


class TestValidation:
    @pytest.mark.parametrize("key", ["Last-Site", "1st", "has space", "x" * 65])
    async def test_a_bad_preference_key_is_422(
        self, clients: tuple[httpx.AsyncClient, httpx.AsyncClient], key: str
    ) -> None:
        ana, _ = clients
        response = await ana.put(f"/api/v1/me/preferences/{key}", json={"value": 1})
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "body",
        [
            {"name": ""},
            {"name": "x", "scale": "log"},
            {"name": "x", "styles": {"101": {"width": 9}}},
            {"name": "x", "unknown": True},
        ],
        ids=["blank-name", "bad-scale", "bad-width", "extra-field"],
    )
    async def test_a_bad_trend_is_422(
        self, clients: tuple[httpx.AsyncClient, httpx.AsyncClient], body: dict[str, object]
    ) -> None:
        ana, _ = clients
        assert (await ana.post("/api/v1/me/trends", json=body)).status_code == 422
