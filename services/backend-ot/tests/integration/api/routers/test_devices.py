"""
Integration tests for /api/devices.

Guards device CRUD against a real database: site scoping, per-site name uniqueness,
standardized-point generation on create, the soft-delete / restore lifecycle, and the PV array
config of a PV or INVERTER device (one per device, replaced whole, gone with the device).
"""

from pydantic import TypeAdapter

from integration.factories import create_device, create_site, device_request
from schemas.api_models import (
    DeviceDeleteResponse,
    DevicePointsCategoryGrouped,
    DeviceUpdate,
    DeviceWithPoints,
    PvArrayConfigResponse,
    PvArrayConfigUpsertRequest,
)
from schemas.tests_models import ApiErrorDetail, ApiErrorResponse

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


PV_ARRAY = PvArrayConfigUpsertRequest(
    tilt_deg=25, azimuth_deg=180, dc_capacity_kw=6500, ac_capacity_kw=5000
)


def pv_array_url(site_id: int, device_id: int) -> str:
    return f"{devices_url(site_id)}/{device_id}/pv-array"


class TestPvArrayConfig:
    async def test_put_creates_then_get_returns_it_with_defaults(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="pv-1", type="PV")
        response = await client.put(
            pv_array_url(site.site_id, device.device_id),
            json=PV_ARRAY.model_dump(mode="json", exclude_unset=True),
        )
        assert response.status_code == 200, response.text
        saved = PvArrayConfigResponse.model_validate(response.json())
        assert (saved.device_id, saved.site_id, saved.device_name, saved.device_type) == (
            device.device_id, site.site_id, "pv-1", "PV"
        )
        assert (saved.tilt_deg, saved.azimuth_deg, saved.dc_capacity_kw, saved.ac_capacity_kw) == (
            25, 180, 6500, 5000
        )
        assert (saved.system_loss_pct, saved.temp_coefficient_pct_per_c) == (14.0, -0.35)

        fetched = await client.get(pv_array_url(site.site_id, device.device_id))
        assert fetched.status_code == 200
        assert PvArrayConfigResponse.model_validate(fetched.json()) == saved

    async def test_put_again_replaces_every_field(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="inv-1", type="INVERTER")
        url = pv_array_url(site.site_id, device.device_id)
        first = await client.put(
            url, json=PV_ARRAY.model_copy(update={"system_loss_pct": 10}).model_dump(mode="json")
        )
        assert first.status_code == 200
        replacement = PvArrayConfigUpsertRequest(
            tilt_deg=10, azimuth_deg=90, dc_capacity_kw=100, ac_capacity_kw=80
        )
        second = await client.put(url, json=replacement.model_dump(mode="json", exclude_unset=True))
        assert second.status_code == 200
        saved = PvArrayConfigResponse.model_validate(second.json())
        assert (saved.tilt_deg, saved.azimuth_deg, saved.dc_capacity_kw, saved.ac_capacity_kw) == (
            10, 90, 100, 80
        )
        assert saved.system_loss_pct == 14.0  # omitted -> default, not the previous 10
        assert saved.created_at == PvArrayConfigResponse.model_validate(first.json()).created_at
        assert saved.updated_at >= saved.created_at

    async def test_wrong_device_type_is_400(self, client):
        site = await create_site(client)
        meter = await create_device(client, site.site_id)
        response = await client.put(
            pv_array_url(site.site_id, meter.device_id), json=PV_ARRAY.model_dump(mode="json")
        )
        assert response.status_code == 400
        error = ApiErrorResponse.model_validate(response.json())
        assert isinstance(error.detail, ApiErrorDetail)
        assert error.detail.error == "ValidationError"

    async def test_device_of_another_site_is_404(self, client):
        site = await create_site(client)
        other = await create_site(client, name="Other Site")
        device = await create_device(client, site.site_id, name="pv-1", type="PV")
        response = await client.put(
            pv_array_url(other.site_id, device.device_id), json=PV_ARRAY.model_dump(mode="json")
        )
        assert response.status_code == 404

    async def test_get_without_config_is_404(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="pv-1", type="PV")
        assert (await client.get(pv_array_url(site.site_id, device.device_id))).status_code == 404

    async def test_out_of_range_values_are_422(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="pv-1", type="PV")
        url = pv_array_url(site.site_id, device.device_id)
        valid = PV_ARRAY.model_dump(mode="json")
        for bad in (
            {"tilt_deg": 91},
            {"azimuth_deg": 360},
            {"dc_capacity_kw": 0},
            {"system_loss_pct": 100},
            {"temp_coefficient_pct_per_c": 0.1},
            {"unknown": 1},
        ):
            response = await client.put(url, json=valid | bad)
            assert response.status_code == 422, bad

    async def test_delete_returns_it_then_404(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="pv-1", type="PV")
        url = pv_array_url(site.site_id, device.device_id)
        await client.put(url, json=PV_ARRAY.model_dump(mode="json"))
        deleted = await client.delete(url)
        assert deleted.status_code == 200
        assert PvArrayConfigResponse.model_validate(deleted.json()).device_id == device.device_id
        assert (await client.get(url)).status_code == 404
        assert (await client.delete(url)).status_code == 404

    async def test_hard_deleting_the_device_deletes_its_config(self, client, db):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="pv-1", type="PV")
        await client.put(
            pv_array_url(site.site_id, device.device_id), json=PV_ARRAY.model_dump(mode="json")
        )
        response = await client.delete(
            f"{devices_url(site.site_id)}/{device.device_id}",
            params={"mode": "hard", "confirm": "true"},
        )
        assert response.status_code == 200, response.text
        assert await db.fetchval("SELECT count(*) FROM pv_array_configs") == 0
