"""The knowledge admin API, and the AI's tools reading what it publishes.

Invariant guarded: only admins (with a session) read or edit a site's knowledge; edits land in
the draft and the AI's tools see them only after a publish; an edit against an older draft
revision is a 409, a secret or an unapproved point a 422, a site that isn't onboarded a 404.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from doubles.services import build_test_services
from fakes import ScriptedLLMClient, as_dict, make_ctx, make_settings
from site_profile_fakes import SITE_ID, backend, mesa

from intelli_gateway.app import create_app
from intelli_gateway.knowledge.published_store import PublishedKnowledgeStore
from intelli_gateway.tools.catalog import build_local_tools
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.local_provider import LocalToolProvider
from intelli_gateway.wiring import Services

PASSWORD = "correct horse battery"
ADMIN = "root@example.com"
ENGINEER = "ana@example.com"
BASE = f"/api/v1/sites/{SITE_ID}/knowledge"
FAULT_GUIDE: dict[str, Any] = {
    "meaning": "Meter fault code",
    "states": [
        {
            "kind": "fault_code",
            "code": 3,
            "label": "CT_OPEN",
            "severity": "fault",
            "message": "A current transformer is open",
            "checks": ["Check the CT wiring"],
        }
    ],
}


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

    async def explain(self, point_name: str) -> dict[str, Any]:
        """What the AI's explain_point tool returns now."""
        limits = SiteToolLimits(
            max_rows=50, history_samples=12, history_max_days=31, max_text_chars=20_000
        )
        store = PublishedKnowledgeStore(self.services.knowledge, self.services.site_profiles)
        provider = LocalToolProvider(
            build_local_tools(self.services.site_data, store, limits), 20_000
        )
        result = await provider.call_tool(
            "explain_point", {"point_name": point_name}, make_ctx(site_id=SITE_ID)
        )
        assert not result.is_error, result.content
        return as_dict(result.content)


@pytest.fixture
async def setup() -> Setup:
    settings = make_settings(ANTHROPIC_API_KEY="test-key")
    services = build_test_services(
        settings,
        llm=ScriptedLLMClient(),
        sites=[mesa()],
        site_data=backend(mesa()),
        knowledge_store=None,  # the production reader: published knowledge only
    )
    await services.auth.create_user(ADMIN, "Root", "admin", PASSWORD)
    await services.auth.create_user(ENGINEER, "Ana", "engineer", PASSWORD)
    return Setup(services, httpx.ASGITransport(app=create_app(settings, services)))


async def test_only_admins_reach_knowledge(setup: Setup) -> None:
    async with setup.client() as anonymous, setup.client(ENGINEER) as engineer:
        assert (await anonymous.get(BASE)).status_code == 401
        assert (await engineer.get(BASE)).status_code == 403
        assert (
            await engineer.put(f"{BASE}/point-guides/1/Fault", json=FAULT_GUIDE)
        ).status_code == 403
        assert (await engineer.post(f"{BASE}/publish", json={})).status_code == 403


async def test_edit_then_publish_reaches_the_ai(setup: Setup) -> None:
    async with setup.client(ADMIN) as admin:
        empty = (await admin.get(BASE)).json()
        assert (empty["published_version"], empty["draft_revision"], empty["changes"]) == (
            None,
            0,
            [],
        )

        saved = await admin.put(
            f"{BASE}/point-guides/1/Fault", json={**FAULT_GUIDE, "draft_revision": 0}
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["draft_revision"] == 1
        assert (await setup.explain("M1.Fault"))["guide"] is None  # a draft: not for the AI yet

        stale = await admin.put(
            f"{BASE}/point-guides/1/Status", json={"meaning": "On/off", "draft_revision": 0}
        )
        assert stale.status_code == 409
        document = await admin.post(
            f"{BASE}/documents",
            json={
                "kind": "procedure",
                "title": "Meter reset",
                "body": "Press reset",
                "draft_revision": 1,
            },
        )
        assert document.status_code == 201 and document.json()["document_id"]
        facts = await admin.put(
            f"{BASE}/device-facts/1",
            json={
                "ratings": [{"name": "CT ratio", "value": 400, "unit": "A/5A"}],
                "draft_revision": 2,
            },
        )
        assert [change["kind"] for change in facts.json()["changes"]] == ["added", "added", "added"]

        published = await admin.post(f"{BASE}/publish", json={"draft_revision": 3})
        assert published.status_code == 200, published.text
        assert published.json()["version"] == 1

        guide = (await setup.explain("M1.Fault"))["guide"]
        assert guide["meaning"] == "Meter fault code"
        assert guide["states"][0]["label"] == "CT_OPEN"
        versions = (await admin.get(f"{BASE}/versions")).json()
        assert [
            (v["version"], v["point_guides"], v["documents"], v["device_facts"]) for v in versions
        ] == [(1, 1, 1, 1)]
        coverage = (await admin.get(f"{BASE}/coverage")).json()
        assert [m["qualified_name"] for m in coverage["missing_guides"]] == ["M1.Status"]


async def test_bad_edits_are_refused(setup: Setup) -> None:
    async with setup.client(ADMIN) as admin:
        secret = await admin.post(
            f"{BASE}/documents",
            json={"kind": "manual", "title": "Login", "body": "password: hunter2"},
        )
        assert secret.status_code == 422 and "never stores" in secret.json()["detail"]
        unknown = await admin.put(f"{BASE}/point-guides/1/Nope", json=FAULT_GUIDE)
        assert unknown.status_code == 422
        nothing = await admin.post(f"{BASE}/publish", json={})
        assert nothing.status_code == 422
        assert (await admin.get("/api/v1/sites/999/knowledge")).status_code == 404


async def test_revert_discard_and_restore(setup: Setup) -> None:
    async with setup.client(ADMIN) as admin:
        await admin.put(f"{BASE}/point-guides/1/Fault", json=FAULT_GUIDE)
        await admin.post(f"{BASE}/publish", json={})
        await admin.put(f"{BASE}/point-guides/1/Fault", json={"meaning": "a mistake"})
        reverted = await admin.post(f"{BASE}/draft/revert", json={"item_keys": ["point:1:Fault"]})
        assert reverted.json()["draft_revision"] == 0  # nothing left to publish: no draft

        await admin.delete(f"{BASE}/point-guides/1/Fault")
        await admin.post(f"{BASE}/publish", json={})  # v2: no guide
        assert (await setup.explain("M1.Fault"))["guide"] is None
        restored = await admin.post(f"{BASE}/versions/1/restore")
        assert (restored.json()["version"], restored.json()["restored_from"]) == (3, 1)
        assert (await setup.explain("M1.Fault"))["guide"]["meaning"] == "Meter fault code"

        await admin.put(f"{BASE}/point-guides/1/Status", json={"meaning": "On/off"})
        assert (await admin.delete(f"{BASE}/draft")).json()["changes"] == []

        created = await admin.post(
            f"{BASE}/site-scripts", json={"name": "Overview", "text": "Solar site, one meter."}
        )
        assert created.status_code == 201
        script_id = created.json()["script_id"]
        assert [s["name"] for s in created.json()["content"]["site_scripts"]] == ["Overview"]
        links = {"points": [{"device_id": 1, "point_name": "Fault"}], "devices": [1]}
        changed = await admin.put(
            f"{BASE}/site-scripts/{script_id}",
            json={"name": "Overview", "text": "Solar site.", "links": links, "draft_revision": 1},
        )
        script = changed.json()["content"]["site_scripts"][0]
        assert script["text"] == "Solar site."
        assert script["links"] == {**links, "functions": [], "documents": []}
        bad_link = await admin.put(
            f"{BASE}/site-scripts/{script_id}",
            json={"name": "Overview", "text": "Solar site.", "links": {"devices": [99]}},
        )
        assert bad_link.status_code == 422 and "device 99" in bad_link.json()["detail"]
        assert (
            await admin.put(f"{BASE}/site-scripts/nope", json={"name": "x", "text": "y"})
        ).status_code == 404
        assert (
            await admin.post(f"{BASE}/site-scripts", json={"name": "", "text": "y"})
        ).status_code == 422
        removed = await admin.delete(f"{BASE}/site-scripts/{script_id}")
        assert removed.json()["content"]["site_scripts"] == [] and removed.json()["changes"] == []

        live = await admin.delete(f"{BASE}/versions", params={"version": [2, 3]})
        assert live.status_code == 422 and "what the AI uses" in live.json()["detail"]
        assert (await admin.delete(f"{BASE}/versions")).status_code == 422
        deleted = await admin.delete(f"{BASE}/versions", params={"version": [1, 2]})
        assert [v["version"] for v in deleted.json()] == [3]
        assert (await setup.explain("M1.Fault"))["guide"]["meaning"] == "Meter fault code"
