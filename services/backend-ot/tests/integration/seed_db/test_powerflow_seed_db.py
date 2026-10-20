"""
Integration tests for the powerflow dev seed (`seed_db.py powerflow <site>`).

Invariant guarded: seeding powerflow's 2bess_1pv site creates its site (no profile), its nine
devices with their served points and scan ranges, and its single line diagram whose links all
resolve; the seeded devices carry the same STANDARDIZED points as API-created ones; reseeding
adds nothing; the PV inverter gets its PV array config and the site its dev
location; and it coexists with the mock-modbus site (devices are matched within their site).
"""

from pydantic import TypeAdapter
from seed_db.seed_db import powerflow_seed_data, seed

from helpers.sites.sld import sld_link_errors
from integration.factories import create_device, create_site
from schemas.api_models import (
    DevicePointResponse,
    DeviceWithPoints,
    PvArrayConfigResponse,
    SiteResponse,
    SiteSldResponse,
)

SITE_LIST = TypeAdapter(list[SiteResponse])
DEVICE_LIST = TypeAdapter(list[DeviceWithPoints])
POINT_LIST = TypeAdapter(list[DevicePointResponse])
PV_ARRAY_LIST = TypeAdapter(list[PvArrayConfigResponse])
POWERFLOW_SITE = "2bess_1pv"


async def site_named(client, name: str) -> SiteResponse:
    sites = SITE_LIST.validate_python((await client.get("/api/sites")).json())
    (site,) = [site for site in sites if site.name == name]
    return site


async def devices_of(client, site: SiteResponse) -> list[DeviceWithPoints]:
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


def point_shape(point: DevicePointResponse) -> tuple[object, ...]:
    return (
        point.name, point.address, point.size, point.data_type, point.category,
        point.scale_factor, point.unit, point.byte_order, point.word_order,
        point.point_class, point.severity,
    )


class TestPowerflowSeed:
    async def test_site_devices_and_points(self, client):
        data = powerflow_seed_data(POWERFLOW_SITE)
        await seed(data)
        site = await site_named(client, data.sites[0].name)
        assert site.profile is None
        devices = {device.name: device for device in await devices_of(client, site)}
        assert set(devices) == {seed_device.device.name for seed_device in data.devices}
        for name, device in devices.items():
            assert device.host == "powerflow" and device.port == 502 and device.server_address == 1
            assert device.read_from_aggregator is False
            assert device.modbus_address_mode == "zero_based"
            expected = sorted(point.name for point in data.device_points[name])
            assert sorted(point.name for point in device.points.native) == expected, name
            # Every point is read by one holding range (ranges split where unserved rows leave gaps).
            assert device.scan_ranges is not None, name
            ranges = device.scan_ranges.holding
            for point in device.points.native:
                assert point.address is not None
                assert any(
                    scan.start_index <= point.address
                    and point.address + point.size <= scan.start_index + scan.count
                    for scan in ranges
                ), f"{name}.{point.name}"

    async def test_standardized_points_match_api_created_devices(self, client):
        data = powerflow_seed_data(POWERFLOW_SITE)
        await seed(data)
        site = await site_named(client, data.sites[0].name)
        api_site = await create_site(client, name="API Site")
        for index, seeded in enumerate(await devices_of(client, site)):
            via_api = await create_device(client, api_site.site_id, name=f"api-{index}", type=seeded.type)
            expected = sorted(map(point_shape, await standardized_points(client, via_api)))
            actual = sorted(map(point_shape, await standardized_points(client, seeded)))
            assert actual == expected, seeded.name

    async def test_sld_links_resolve(self, client):
        data = powerflow_seed_data(POWERFLOW_SITE)
        await seed(data)
        site = await site_named(client, data.sites[0].name)
        response = await client.get(f"/api/sites/{site.site_id}/sld")
        assert response.status_code == 200, response.text
        stored = SiteSldResponse.model_validate(response.json())
        assert sld_link_errors(stored.sld, await devices_of(client, site)) == []
        linked = {node.id for node in stored.sld.nodes if node.device is not None}
        assert {"poi_meter", "bess1", "bess2", "pv1"} <= linked

    async def test_reseeding_adds_nothing(self, client):
        data = powerflow_seed_data(POWERFLOW_SITE)
        await seed(data)
        site = await site_named(client, data.sites[0].name)
        before = {device.name: len(device.points.native) for device in await devices_of(client, site)}
        await seed(powerflow_seed_data(POWERFLOW_SITE))
        after = {device.name: len(device.points.native) for device in await devices_of(client, site)}
        assert after == before
        assert len(SITE_LIST.validate_python((await client.get("/api/sites")).json())) == 1

    async def test_coexists_with_the_mock_modbus_site(self, client):
        await seed()
        await seed(powerflow_seed_data(POWERFLOW_SITE))
        sites = SITE_LIST.validate_python((await client.get("/api/sites")).json())
        assert {site.name for site in sites} == {"Alpha Solar Farm", "Powerflow 2BESS 1PV"}
        alpha = await site_named(client, "Alpha Solar Farm")
        assert {device.host for device in await devices_of(client, alpha)} == {"mock-modbus"}

    async def test_pv_array_and_location(self, client):
        data = powerflow_seed_data(POWERFLOW_SITE)
        await seed(data)
        site = await site_named(client, data.sites[0].name)
        assert site.coordinates == data.sites[0].coordinates
        assert site.coordinates is not None and site.coordinates.elevation_m is not None
        assert site.timezone == data.sites[0].timezone
        response = await client.get(f"/api/sites/{site.site_id}/pv-arrays")
        assert response.status_code == 200, response.text
        arrays = PV_ARRAY_LIST.validate_python(response.json())
        assert {array.device_name: array.dc_capacity_kw for array in arrays} == {
            name: config.dc_capacity_kw for name, config in data.pv_arrays.items()
        }
        assert all(array.device_type == "PV" for array in arrays)

    async def test_reseeding_keeps_an_edited_pv_array(self, client):
        data = powerflow_seed_data(POWERFLOW_SITE)
        await seed(data)
        site = await site_named(client, data.sites[0].name)
        (array,) = PV_ARRAY_LIST.validate_python(
            (await client.get(f"/api/sites/{site.site_id}/pv-arrays")).json()
        )
        edited = data.pv_arrays[array.device_name].model_copy(update={"tilt_deg": 5.0})
        url = f"/api/devices/site/{site.site_id}/devices/{array.device_id}/pv-array"
        assert (await client.put(url, json=edited.model_dump(mode="json"))).status_code == 200
        await seed(data)
        after = PvArrayConfigResponse.model_validate((await client.get(url)).json())
        assert after.tilt_deg == 5.0
