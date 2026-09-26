"""
Integration tests for the dev seeder (tests/seed_db/seed_db.py).

Invariant guarded: a device the seeder creates ends up with the same STANDARDIZED points as a
device of the same type created through POST /api/devices/site/{site_id}/devices. The seeder
writes rows directly rather than calling the API, so without this check any create-time
behaviour added to the API is silently missing from the dev data. Also guards idempotency.
"""

from pydantic import TypeAdapter
from seed_db.seed_db import DEVICES, SITES, seed

from integration.factories import create_device, create_site
from schemas.api_models import DevicePointResponse, DeviceWithPoints, SiteResponse

SITE_LIST = TypeAdapter(list[SiteResponse])
DEVICE_LIST = TypeAdapter(list[DeviceWithPoints])
POINT_LIST = TypeAdapter(list[DevicePointResponse])


def point_shape(point: DevicePointResponse) -> tuple[object, ...]:
    """Everything a point carries except its ids and timestamps."""
    return (
        point.name, point.address, point.size, point.data_type, point.category,
        point.scale_factor, point.unit, point.byte_order, point.word_order,
        point.point_class, point.severity,
    )


async def seeded_devices(client) -> list[DeviceWithPoints]:
    sites = SITE_LIST.validate_python((await client.get("/api/sites")).json())
    (site,) = [site for site in sites if site.name == SITES[0].name]
    response = await client.get(f"/api/devices/site/{site.site_id}/devices")
    assert response.status_code == 200, response.text
    return DEVICE_LIST.validate_python(response.json())


async def standardized_points(client, device: DeviceWithPoints) -> list[DevicePointResponse]:
    response = await client.get(
        f"/api/device-points/site/{device.site_id}/device/{device.device_id}",
        params={"category": "STANDARDIZED"},
    )
    assert response.status_code == 200, response.text
    return POINT_LIST.validate_python(response.json())


class TestSeedStandardizedPoints:
    async def test_seeded_devices_match_devices_created_through_the_api(self, client):
        await seed()
        devices = await seeded_devices(client)
        assert {device.name for device in devices} == {seed_device.device.name for seed_device in DEVICES}

        api_site = await create_site(client, name="API Site")
        for index, seeded in enumerate(devices):
            via_api = await create_device(
                client, api_site.site_id, name=f"api-{index}", type=seeded.type
            )
            expected = sorted(map(point_shape, await standardized_points(client, via_api)))
            actual = sorted(map(point_shape, await standardized_points(client, seeded)))
            assert expected, f"no standardized template for type {seeded.type}"
            assert actual == expected, seeded.name

    async def test_reseeding_creates_no_duplicates(self, client):
        await seed()
        await seed()
        for device in await seeded_devices(client):
            names = [point.name for point in await standardized_points(client, device)]
            assert len(names) == len(set(names)) == 3, device.name

    async def test_points_are_created_in_api_order(self, client):
        """Per device, STANDARDIZED then NATIVE (then VIRTUAL), device after device: the ids the
        API produces when a device is created and its native points are added afterwards."""
        await seed()
        category_rank = {"STANDARDIZED": 0, "NATIVE": 1, "VIRTUAL": 2}
        previous_device_max_id = 0
        for device in sorted(await seeded_devices(client), key=lambda device: device.device_id):
            response = await client.get(
                f"/api/device-points/site/{device.site_id}/device/{device.device_id}"
            )
            assert response.status_code == 200, response.text
            points = sorted(POINT_LIST.validate_python(response.json()), key=lambda p: p.id)
            ranks = [category_rank[point.category] for point in points]
            assert ranks == sorted(ranks), f"{device.name}: categories out of order by id"
            assert points[0].id > previous_device_max_id, f"{device.name}: ids interleave"
            previous_device_max_id = points[-1].id
