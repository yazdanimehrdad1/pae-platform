"""
Integration tests for /api/sites.

Guards site CRUD against a real database: name uniqueness, the soft-delete / restore
lifecycle (which cascades to devices and points), and the guard rails on hard delete.
"""

from pydantic import TypeAdapter

from integration.factories import create_device, create_site, site_request
from schemas.api_models import (
    SiteComprehensiveResponse,
    SiteDeleteResponse,
    SiteResponse,
    SiteUpdateRequest,
)
from schemas.tests_models import ApiErrorDetail, ApiErrorResponse

SITE_LIST = TypeAdapter(list[SiteResponse])


class TestCreateSite:
    async def test_create_returns_201_and_persists(self, client):
        response = await client.post("/api/sites", json=site_request().model_dump(mode="json"))
        assert response.status_code == 201
        created = SiteResponse.model_validate(response.json())
        assert created.site_id == 1001  # sites_id_seq starts at 1001
        assert created.name == "Test Site"
        assert created.device_count == 0
        assert created.deleted_at is None

        fetched = await client.get(f"/api/sites/{created.site_id}")
        assert fetched.status_code == 200
        fetched_site = SiteResponse.model_validate(fetched.json())
        assert fetched_site.location is not None
        assert fetched_site.location.city == "Fresno"

    async def test_duplicate_name_is_409(self, client):
        await create_site(client)
        response = await client.post("/api/sites", json=site_request().model_dump(mode="json"))
        assert response.status_code == 409
        error = ApiErrorResponse.model_validate(response.json())
        assert isinstance(error.detail, ApiErrorDetail)
        assert error.detail.error == "ConflictError"

    async def test_invalid_payload_is_422(self, client):
        # Deliberately invalid: an empty name can't be built as a SiteCreateRequest.
        payload = site_request().model_dump(mode="json") | {"name": ""}
        response = await client.post("/api/sites", json=payload)
        assert response.status_code == 422


class TestSiteProfile:
    async def test_create_with_registered_profile_persists_it(self, client):
        site = await create_site(client, profile="alpha_solar")
        assert site.profile == "alpha_solar"
        fetched = SiteResponse.model_validate((await client.get(f"/api/sites/{site.site_id}")).json())
        assert fetched.profile == "alpha_solar"

    async def test_create_without_profile_uses_default(self, client):
        # Deliberately omit profile, as a client that doesn't know about profiles would.
        payload = site_request().model_dump(mode="json", exclude={"profile"})
        response = await client.post("/api/sites", json=payload)
        assert response.status_code == 201
        assert SiteResponse.model_validate(response.json()).profile == "default"

    async def test_create_with_unknown_profile_is_400(self, client):
        payload = site_request(profile="no_such_site").model_dump(mode="json")
        response = await client.post("/api/sites", json=payload)
        assert response.status_code == 400
        error = ApiErrorResponse.model_validate(response.json())
        assert isinstance(error.detail, ApiErrorDetail)
        assert error.detail.error == "ValidationError"

    async def test_update_switches_default_to_site_profile(self, client):
        site = await create_site(client)
        assert site.profile == "default"
        body = SiteUpdateRequest(profile="alpha_solar").model_dump(mode="json", exclude_unset=True)
        response = await client.put(f"/api/sites/{site.site_id}", json=body)
        assert response.status_code == 200
        assert SiteResponse.model_validate(response.json()).profile == "alpha_solar"

    async def test_update_without_profile_keeps_it(self, client):
        site = await create_site(client, profile="alpha_solar")
        body = SiteUpdateRequest(operator="New Operator").model_dump(mode="json", exclude_unset=True)
        response = await client.put(f"/api/sites/{site.site_id}", json=body)
        assert SiteResponse.model_validate(response.json()).profile == "alpha_solar"

    async def test_update_to_unknown_profile_is_400(self, client):
        site = await create_site(client)
        body = SiteUpdateRequest(profile="no_such_site").model_dump(mode="json", exclude_unset=True)
        response = await client.put(f"/api/sites/{site.site_id}", json=body)
        assert response.status_code == 400


class TestReadSites:
    async def test_list_excludes_soft_deleted_unless_asked(self, client):
        kept = await create_site(client, name="Kept")
        dropped = await create_site(client, name="Dropped")
        await client.delete(f"/api/sites/{dropped.site_id}")

        active = SITE_LIST.validate_python((await client.get("/api/sites")).json())
        assert [site.site_id for site in active] == [kept.site_id]

        everything = SITE_LIST.validate_python(
            (await client.get("/api/sites", params={"include_deleted": True})).json()
        )
        assert {site.site_id for site in everything} == {kept.site_id, dropped.site_id}

    async def test_unknown_site_is_404(self, client):
        response = await client.get("/api/sites/9999")
        assert response.status_code == 404


class TestUpdateSite:
    async def test_partial_update_changes_only_given_fields(self, client):
        site = await create_site(client)
        body = SiteUpdateRequest(operator="New Operator").model_dump(
            mode="json", exclude_unset=True
        )
        response = await client.put(f"/api/sites/{site.site_id}", json=body)
        assert response.status_code == 200
        updated = SiteResponse.model_validate(response.json())
        assert updated.operator == "New Operator"
        assert updated.name == site.name

    async def test_rename_to_existing_name_is_409(self, client):
        await create_site(client, name="Alpha")
        beta = await create_site(client, name="Beta")
        body = SiteUpdateRequest(name="Alpha").model_dump(mode="json", exclude_unset=True)
        response = await client.put(f"/api/sites/{beta.site_id}", json=body)
        assert response.status_code == 409

    async def test_update_unknown_site_is_404(self, client):
        body = SiteUpdateRequest(operator="x").model_dump(mode="json", exclude_unset=True)
        response = await client.put("/api/sites/9999", json=body)
        assert response.status_code == 404


class TestDeleteAndRestoreSite:
    async def test_soft_delete_cascades_and_restore_brings_everything_back(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)

        deleted = await client.delete(f"/api/sites/{site.site_id}")
        assert deleted.status_code == 200
        assert SiteDeleteResponse.model_validate(deleted.json()) == SiteDeleteResponse(
            site_id=site.site_id, mode="soft"
        )
        assert (await client.get(f"/api/sites/{site.site_id}")).status_code == 404
        device_url = f"/api/devices/site/{site.site_id}/devices/{device.device_id}"
        assert (await client.get(device_url)).status_code == 404

        restored = await client.post(f"/api/sites/{site.site_id}/restore")
        assert restored.status_code == 200
        assert SiteResponse.model_validate(restored.json()).deleted_at is None
        assert (await client.get(device_url)).status_code == 200

    async def test_restore_active_site_is_409(self, client):
        site = await create_site(client)
        response = await client.post(f"/api/sites/{site.site_id}/restore")
        assert response.status_code == 409

    async def test_hard_delete_requires_confirm(self, client):
        site = await create_site(client)
        response = await client.delete(f"/api/sites/{site.site_id}", params={"mode": "hard"})
        assert response.status_code == 400
        assert (await client.get(f"/api/sites/{site.site_id}")).status_code == 200

    async def test_hard_delete_blocked_by_active_devices(self, client):
        site = await create_site(client)
        await create_device(client, site.site_id)
        response = await client.delete(
            f"/api/sites/{site.site_id}", params={"mode": "hard", "confirm": True}
        )
        assert response.status_code == 409

    async def test_hard_delete_removes_site_permanently(self, client):
        site = await create_site(client)
        response = await client.delete(
            f"/api/sites/{site.site_id}", params={"mode": "hard", "confirm": True}
        )
        assert response.status_code == 200
        assert SiteDeleteResponse.model_validate(response.json()).mode == "hard"
        lookup = await client.get(f"/api/sites/{site.site_id}", params={"include_deleted": True})
        assert lookup.status_code == 404

    async def test_delete_unknown_site_is_404(self, client):
        response = await client.delete("/api/sites/9999")
        assert response.status_code == 404


class TestComprehensiveSite:
    async def test_includes_devices_with_categorized_points(self, client):
        site = await create_site(client)
        await create_device(client, site.site_id, name="bess-1", type="BESS")

        response = await client.get(f"/api/sites/comprehensive/{site.site_id}")
        assert response.status_code == 200
        comprehensive = SiteComprehensiveResponse.model_validate(response.json())
        assert [device.name for device in comprehensive.devices] == ["bess-1"]
        # BESS has standardized-point templates, generated on device creation.
        assert comprehensive.devices[0].points.standardized

    async def test_unknown_site_is_404(self, client):
        response = await client.get("/api/sites/comprehensive/9999")
        assert response.status_code == 404
