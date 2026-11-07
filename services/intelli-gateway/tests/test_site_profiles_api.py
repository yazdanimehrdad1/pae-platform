"""The site profile admin API, and its effect on what users and the AI can reach.

Invariant guarded: only admins (with a session) see and approve site profiles; onboarding goes
sync -> review -> approve, and only then does the site appear in /v1/sites and accept questions;
approving against an older read of backend-ot is a 409, an unknown change a 422; a sync while
backend-ot is down is a 503 and changes nothing.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import pytest
from backend_ot_fake import FakeBackendOt
from doubles.services import build_test_services
from doubles.site_profile_store import InMemorySiteProfileStore
from fakes import ScriptedLLMClient, fixed_clock, make_settings
from site_profile_fakes import SITE_ID, backend, mesa

from intelli_gateway.app import create_app
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_data import BackendOtSiteDataConnector
from intelli_gateway.wiring import Services

PASSWORD = "correct horse battery"
ADMIN = "root@example.com"
ENGINEER = "ana@example.com"


@dataclass
class Setup:
    services: Services
    transport: httpx.ASGITransport

    @asynccontextmanager
    async def client(self, email: str | None = None) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(transport=self.transport, base_url="http://test") as client:
            if email:
                response = await client.post(
                    "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
                )
                assert response.status_code == 200, response.text
            yield client


async def make_setup(site_data: SiteDataConnector) -> Setup:
    # Nothing onboarded yet: an empty profile store.
    settings = make_settings(ANTHROPIC_API_KEY="test-key")
    services = build_test_services(
        settings,
        llm=ScriptedLLMClient(),
        site_data=site_data,
        site_profile_store=InMemorySiteProfileStore(),
    )
    await services.auth.create_user(ADMIN, "Root", "admin", PASSWORD)
    await services.auth.create_user(ENGINEER, "Ana", "engineer", PASSWORD)
    return Setup(services, httpx.ASGITransport(app=create_app(settings, services)))


@pytest.fixture
async def setup() -> Setup:
    return await make_setup(backend(mesa()))


async def test_only_admins_reach_site_profiles(setup: Setup) -> None:
    async with setup.client() as anonymous, setup.client(ENGINEER) as engineer:
        assert (await anonymous.get("/api/v1/site-profiles")).status_code == 401
        assert (await engineer.get("/api/v1/site-profiles")).status_code == 403
        assert (await engineer.post(f"/api/v1/sites/{SITE_ID}/profile/sync")).status_code == 403
        assert (
            await engineer.post(f"/api/v1/sites/{SITE_ID}/profile/approve", json={})
        ).status_code == 403


async def test_onboarding_makes_the_site_available(setup: Setup) -> None:
    async with setup.client(ADMIN) as admin, setup.client(ENGINEER) as engineer:
        assert (await admin.get(f"/api/v1/sites/{SITE_ID}/profile/changes")).status_code == 404

        synced = await admin.post(f"/api/v1/sites/{SITE_ID}/profile/sync")
        assert synced.status_code == 200, synced.text
        pending = synced.json()
        assert [change["change_id"] for change in pending["changes"]] == [
            "site",
            "device:1",
            "topology",
        ]
        assert (await engineer.get("/api/v1/sites")).json() == []
        asked = await engineer.post(f"/api/v1/sites/{SITE_ID}/ask", json={"question": "hi"})
        assert asked.status_code == 404
        assert (await admin.get(f"/api/v1/sites/{SITE_ID}/profile")).status_code == 404

        approved = await admin.post(
            f"/api/v1/sites/{SITE_ID}/profile/approve",
            json={"fetched_at": pending["fetched_at"]},
        )
        assert approved.status_code == 200, approved.text
        assert (approved.json()["version"], approved.json()["approved_by"]) == (1, ADMIN)

        sites = (await engineer.get("/api/v1/sites")).json()
        assert [site["site_id"] for site in sites] == [SITE_ID]
        profile = (await admin.get(f"/api/v1/sites/{SITE_ID}/profile")).json()
        assert len(profile["catalog"]["points"]) == 3
        versions = (await admin.get(f"/api/v1/sites/{SITE_ID}/profile/versions")).json()
        assert [(v["version"], v["devices"], v["points"]) for v in versions] == [(1, 1, 3)]
        statuses = (await admin.get("/api/v1/site-profiles")).json()
        assert [(s["site_id"], s["approved_version"], s["pending_changes"]) for s in statuses] == [
            (SITE_ID, 1, 0)
        ]


async def test_bad_approvals_are_refused(setup: Setup) -> None:
    async with setup.client(ADMIN) as admin:
        pending = (await admin.post(f"/api/v1/sites/{SITE_ID}/profile/sync")).json()
        approve = f"/api/v1/sites/{SITE_ID}/profile/approve"
        stale = await admin.post(approve, json={"fetched_at": "2026-06-15T11:00:00Z"})
        assert stale.status_code == 409
        unknown = await admin.post(approve, json={"change_ids": ["device:99"]})
        assert unknown.status_code == 422
        assert "device:99" in unknown.json()["detail"]
        assert (await admin.get(f"/api/v1/sites/{SITE_ID}/profile")).status_code == 404
        ok = await admin.post(approve, json={"fetched_at": pending["fetched_at"]})
        assert ok.status_code == 200


async def test_a_sync_while_backend_ot_is_down_is_a_503() -> None:
    fake_backend = FakeBackendOt()

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    fake_backend.override = down
    client = BackendOtClient("http://backend-ot.test", 1, 1, transport=fake_backend.transport())
    setup = await make_setup(
        BackendOtSiteDataConnector(client, stale_after_s=600, clock=fixed_clock)
    )
    async with setup.client(ADMIN) as admin:
        response = await admin.post("/api/v1/sites/7/profile/sync")
        assert response.status_code == 503
        assert "backend-ot" in response.json()["detail"]
        assert (await admin.get("/api/v1/site-profiles")).json() == []
