"""
Integration tests for /api/devices.

Guards device CRUD against a real database: site scoping, per-site name uniqueness,
standardized-point generation on create, and the soft-delete / restore lifecycle.
"""

from pydantic import TypeAdapter

from integration.factories import create_device, create_site, device_request
from schemas.api_models import (
    DeviceDeleteResponse,
    DevicePointsCategoryGrouped,
    DeviceUpdate,
    DeviceWithPoints,
)

DEVICE_LIST = TypeAdapter(list[DeviceWithPoints])


def devices_url(site_id: int) -> str:
    return f"/api/devices/site/{site_id}/devices"


class TestCreateDevice:
    async def test_create_returns_201_with_defaults(self, client):
        site = await create_site(client)
        response = await client.post(
            devices_url(site.site_id), json=device_request().model_dump(mode="json")
        )
        assert response.status_code == 201
        device = DeviceWithPoints.model_validate(response.json())
        assert device.site_id == site.site_id
        assert device.type == "METER"
        assert device.protocol == "Modbus"
        assert device.modbus_address_mode == "zero_based"
        assert device.points == DevicePointsCategoryGrouped()

    async def test_device_type_with_templates_gets_standardized_points(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="bess-1", type="BESS")
        # Read back via GET: the POST response is built before the standardized points
        # are generated, so its points are empty even though the rows exist.
        fetched = DeviceWithPoints.model_validate(
            (await client.get(f"{devices_url(site.site_id)}/{device.device_id}")).json()
        )
        standardized = fetched.points.standardized
        assert standardized
        assert all(point.category == "STANDARDIZED" for point in standardized)

    async def test_type_casing_is_normalized(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, type="relay")
        assert device.type == "RELAY"

    async def test_unknown_site_is_404(self, client):
        response = await client.post(
            devices_url(9999), json=device_request().model_dump(mode="json")
        )
        assert response.status_code == 404

    async def test_duplicate_name_in_same_site_is_409(self, client):
        site = await create_site(client)
        await create_device(client, site.site_id)
        response = await client.post(
            devices_url(site.site_id), json=device_request().model_dump(mode="json")
        )
        assert response.status_code == 409

    async def test_same_name_in_different_sites_is_allowed(self, client):
        first_site = await create_site(client, name="Site A")
        second_site = await create_site(client, name="Site B")
        await create_device(client, first_site.site_id)
        await create_device(client, second_site.site_id)

    async def test_invalid_type_is_422(self, client):
        site = await create_site(client)
        # Deliberately invalid: SOLAR isn't a DeviceType, so it can't be built as a model.
        payload = device_request().model_dump(mode="json") | {"type": "SOLAR"}
        response = await client.post(devices_url(site.site_id), json=payload)
        assert response.status_code == 422


class TestReadDevices:
    async def test_list_is_scoped_to_the_site(self, client):
        first_site = await create_site(client, name="Site A")
        second_site = await create_site(client, name="Site B")
        await create_device(client, first_site.site_id, name="a-meter")
        await create_device(client, second_site.site_id, name="b-meter")

        response = await client.get(devices_url(first_site.site_id))
        assert response.status_code == 200
        devices = DEVICE_LIST.validate_python(response.json())
        assert [device.name for device in devices] == ["a-meter"]

    async def test_device_from_another_site_is_404(self, client):
        first_site = await create_site(client, name="Site A")
        second_site = await create_site(client, name="Site B")
        device = await create_device(client, first_site.site_id)
        response = await client.get(f"{devices_url(second_site.site_id)}/{device.device_id}")
        assert response.status_code == 404


class TestUpdateDevice:
    async def test_partial_update(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        response = await client.put(
            f"{devices_url(site.site_id)}/{device.device_id}",
            json=DeviceUpdate(port=1502, poll_enabled=False).model_dump(
                mode="json", exclude_unset=True
            ),
        )
        assert response.status_code == 200
        updated = DeviceWithPoints.model_validate(response.json())
        assert updated.port == 1502
        assert updated.poll_enabled is False
        assert updated.host == device.host

    async def test_update_unknown_device_is_404(self, client):
        site = await create_site(client)
        body = DeviceUpdate(port=1502).model_dump(mode="json", exclude_unset=True)
        response = await client.put(f"{devices_url(site.site_id)}/9999", json=body)
        assert response.status_code == 404


class TestDeleteAndRestoreDevice:
    async def test_soft_delete_then_restore(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        device_url = f"{devices_url(site.site_id)}/{device.device_id}"

        deleted = await client.delete(device_url)
        assert deleted.status_code == 200
        assert DeviceDeleteResponse.model_validate(deleted.json()).mode == "soft"
        assert (await client.get(device_url)).status_code == 404
        assert (await client.get(device_url, params={"include_deleted": True})).status_code == 200

        restored = await client.post(f"{device_url}/restore")
        assert restored.status_code == 200
        assert DeviceWithPoints.model_validate(restored.json()).deleted_at is None

    async def test_soft_deleted_name_blocks_reuse(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        await client.delete(f"{devices_url(site.site_id)}/{device.device_id}")
        response = await client.post(
            devices_url(site.site_id), json=device_request().model_dump(mode="json")
        )
        assert response.status_code == 409

    async def test_restore_active_device_is_409(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        response = await client.post(f"{devices_url(site.site_id)}/{device.device_id}/restore")
        assert response.status_code == 409

    async def test_hard_delete_requires_confirm(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        response = await client.delete(
            f"{devices_url(site.site_id)}/{device.device_id}", params={"mode": "hard"}
        )
        assert response.status_code == 400

    async def test_hard_delete_frees_the_name(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id)
        response = await client.delete(
            f"{devices_url(site.site_id)}/{device.device_id}",
            params={"mode": "hard", "confirm": True},
        )
        assert response.status_code == 200
        assert DeviceDeleteResponse.model_validate(response.json()).mode == "hard"
        await create_device(client, site.site_id)

    async def test_delete_unknown_device_is_404(self, client):
        site = await create_site(client)
        response = await client.delete(f"{devices_url(site.site_id)}/9999")
        assert response.status_code == 404
