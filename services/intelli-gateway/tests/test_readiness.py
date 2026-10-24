"""GET /api/readyz: ready when its own Postgres answers, or when none is configured (forecasts in
memory); 503 with database=unavailable when the configured database doesn't answer. The deploy
waits on it, so it must never report ready over a dead database."""

import httpx
import pytest
from fakes import ScriptedLLMClient, fixed_clock

import intelli_gateway.api.routers.health as health
from intelli_gateway.app import create_app
from intelli_gateway.config import Settings
from intelli_gateway.schemas.api_models.responses import ReadinessResponse
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.wiring import build_services

# Never connected to: the database check is replaced in these tests.
UNUSED_DATABASE_URL = "postgresql+asyncpg://user:password@db.invalid:5432/intelli_gateway"


def make_client(settings: Settings, with_database: bool) -> httpx.AsyncClient:
    services = build_services(settings, llm=ScriptedLLMClient(), clock=fixed_clock)
    if with_database:
        services.database = create_database_engine(UNUSED_DATABASE_URL)
    app = create_app(settings, services)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def answer(reachable: bool) -> object:
    async def database_is_reachable(engine: object) -> bool:
        return reachable

    return database_is_reachable


class TestReadyz:
    async def test_ready_without_a_configured_database(self, settings: Settings) -> None:
        async with make_client(settings, with_database=False) as client:
            response = await client.get("/api/readyz")

        assert response.status_code == 200
        assert ReadinessResponse.model_validate(response.json()) == ReadinessResponse(
            ok=True, database="not_configured"
        )

    async def test_ready_when_the_database_answers(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(health, "database_is_reachable", answer(True))
        async with make_client(settings, with_database=True) as client:
            response = await client.get("/api/readyz")

        assert response.status_code == 200
        assert ReadinessResponse.model_validate(response.json()) == ReadinessResponse(
            ok=True, database="ok"
        )

    async def test_503_when_the_database_is_unreachable(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(health, "database_is_reachable", answer(False))
        async with make_client(settings, with_database=True) as client:
            response = await client.get("/api/readyz")

        assert response.status_code == 503
        assert ReadinessResponse.model_validate(response.json()) == ReadinessResponse(
            ok=False, database="unavailable"
        )

    async def test_healthz_stays_dependency_free(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(health, "database_is_reachable", answer(False))
        async with make_client(settings, with_database=True) as client:
            response = await client.get("/api/healthz")

        assert response.status_code == 200
