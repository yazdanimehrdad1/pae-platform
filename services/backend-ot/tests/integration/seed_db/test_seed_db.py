"""
Integration tests for the dev seeder (tests/seed_db/seed_db.py).

Invariant guarded: a device the seeder creates ends up with the same STANDARDIZED points as a
device of the same type created through POST /api/devices/site/{site_id}/devices. The seeder
writes rows directly rather than calling the API, so without this check any create-time
behaviour added to the API is silently missing from the dev data. Likewise for VIRTUAL points,
which the seeder builds with the create path's own builder. Also guards idempotency, and that
the seed site's single line diagram is written to site_slds once and never over a saved edit.
"""

from pydantic import TypeAdapter
from seed_db.seed_db import DEVICES, SITE_SLDS, SITES, seed, user_alarms, virtual_points

from integration.factories import create_alarm, create_device, create_site, create_virtual_point
from schemas.api_models import (
    DevicePointResponse,
    DeviceWithPoints,
    SiteResponse,
    SiteSldResponse,
    SiteSldUpsertRequest,
)
from schemas.api_models.alarms import AlarmDefinitionResponse

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
        """Per device, STANDARDIZED then NATIVE, device after device: the ids the API produces
        when a device is created and its native points are added afterwards. VIRTUAL points come
        after every device's points, since they read points on other devices."""
        await seed()
        category_rank = {"STANDARDIZED": 0, "NATIVE": 1}
        previous_device_max_id = 0
        virtual_ids: list[int] = []
        for device in sorted(await seeded_devices(client), key=lambda device: device.device_id):
            response = await client.get(
                f"/api/device-points/site/{device.site_id}/device/{device.device_id}"
            )
            assert response.status_code == 200, response.text
            all_points = POINT_LIST.validate_python(response.json())
            virtual_ids += [point.id for point in all_points if point.category == "VIRTUAL"]
            points = sorted((p for p in all_points if p.category != "VIRTUAL"), key=lambda p: p.id)
            ranks = [category_rank[point.category] for point in points]
            assert ranks == sorted(ranks), f"{device.name}: categories out of order by id"
            assert points[0].id > previous_device_max_id, f"{device.name}: ids interleave"
            previous_device_max_id = points[-1].id
        assert virtual_ids, "the seed defines virtual points"
        assert min(virtual_ids) > previous_device_max_id, "virtual points must come after every device's points"


class TestSeedVirtualPoints:
    """A seeded virtual point equals one created through POST .../virtual with the same request."""

    async def test_seeded_virtual_points_match_points_created_through_the_api(self, client):
        await seed()
        devices = {device.name: device for device in await seeded_devices(client)}
        ids_by_name: dict[tuple[str, str], int] = {}
        for device in devices.values():
            response = await client.get(f"/api/device-points/site/{device.site_id}/device/{device.device_id}")
            for point in POINT_LIST.validate_python(response.json()):
                ids_by_name[(device.name, point.name)] = point.id

        for seed_point in virtual_points(lambda device_name, point_name: ids_by_name[(device_name, point_name)]):
            device = devices[seed_point.device_name]
            response = await client.get(
                f"/api/device-points/site/{device.site_id}/device/{device.device_id}",
                params={"category": "VIRTUAL"},
            )
            (seeded,) = [p for p in POINT_LIST.validate_python(response.json()) if p.name == seed_point.point.name]

            api_request = seed_point.point.model_copy(update={"name": f"api_{seed_point.point.name}"})
            via_api = await create_virtual_point(client, device.site_id, device.device_id, api_request)

            assert point_shape(seeded)[1:] == point_shape(via_api)[1:], seed_point.point.name
            assert (seeded.enum_detail, seeded.virtual_definition) == (via_api.enum_detail, via_api.virtual_definition)

    async def test_reseeding_creates_no_duplicate_virtual_points(self, client):
        await seed()
        await seed()
        for device in await seeded_devices(client):
            response = await client.get(
                f"/api/device-points/site/{device.site_id}/device/{device.device_id}",
                params={"category": "VIRTUAL"},
            )
            names = [point.name for point in POINT_LIST.validate_python(response.json())]
            assert len(names) == len(set(names)), device.name


ALARM_LIST = TypeAdapter(list[AlarmDefinitionResponse])


def alarm_shape(alarm: AlarmDefinitionResponse) -> tuple[object, ...]:
    """Everything an alarm carries except its id, name and timestamps."""
    return (alarm.source, alarm.kind, alarm.rule, alarm.severity, alarm.message, alarm.enabled,
            alarm.notify_mobile, alarm.notify_email, alarm.profile_alarm_key)


class TestSeedAlarms:
    """Seeded user alarms equal ones created through POST .../definitions; the seed site gets its
    profile's alarms, as a site created through POST /api/sites does; reseeding adds nothing."""

    async def seeded_site(self, client) -> SiteResponse:
        sites = SITE_LIST.validate_python((await client.get("/api/sites")).json())
        (site,) = [site for site in sites if site.name == SITES[0].name]
        return site

    async def test_seeded_user_alarms_match_alarms_created_through_the_api(self, client):
        await seed()
        site = await self.seeded_site(client)
        alarms = {alarm.name: alarm for alarm in ALARM_LIST.validate_python(
            (await client.get(f"/api/alarms/site/{site.site_id}/definitions")).json()
        )}
        devices = {device.name: device for device in await seeded_devices(client)}
        point_ids = {}
        for device in devices.values():
            response = await client.get(f"/api/device-points/site/{device.site_id}/device/{device.device_id}")
            for point in POINT_LIST.validate_python(response.json()):
                point_ids[(device.name, point.name)] = point.id

        seed_alarms = user_alarms(
            lambda device_name, point_name: point_ids[(device_name, point_name)],
            lambda device_name: devices[device_name].device_id,
        )
        assert seed_alarms
        for seed_alarm in seed_alarms:
            via_api = await create_alarm(client, site.site_id, seed_alarm.alarm.model_copy(
                update={"name": f"api_{seed_alarm.alarm.name}"}
            ))
            seeded = alarms[seed_alarm.alarm.name]
            assert alarm_shape(seeded)[:-1] == alarm_shape(via_api)[:-1], seed_alarm.alarm.name

    async def test_the_seed_site_gets_its_profiles_alarms_once(self, client):
        await seed()
        await seed()
        site = await self.seeded_site(client)
        alarms = ALARM_LIST.validate_python((await client.get(f"/api/alarms/site/{site.site_id}/definitions")).json())
        names = [alarm.name for alarm in alarms]
        assert len(names) == len(set(names))
        assert [alarm.profile_alarm_key for alarm in alarms if alarm.source == "PROFILE"] == ["placeholder_profile_alarm_1"]


class TestSeededSld:
    async def seeded_site(self, client) -> SiteResponse:
        sites = SITE_LIST.validate_python((await client.get("/api/sites")).json())
        (site,) = [site for site in sites if site.name == SITES[0].name]
        return site

    async def test_the_seed_site_gets_its_sld_at_revision_1(self, client):
        await seed()
        site = await self.seeded_site(client)
        response = await client.get(f"/api/sites/{site.site_id}/sld")
        assert response.status_code == 200, response.text
        stored = SiteSldResponse.model_validate(response.json())
        assert stored.revision == 1
        assert stored.sld == SITE_SLDS[SITES[0].name]

    async def test_reseeding_keeps_an_sld_saved_through_the_api(self, client):
        await seed()
        site = await self.seeded_site(client)
        edited = SITE_SLDS[SITES[0].name].model_copy(update={"connections": ()})
        body = SiteSldUpsertRequest(sld=edited, revision=1).model_dump(mode="json")
        assert (await client.put(f"/api/sites/{site.site_id}/sld", json=body)).status_code == 200

        await seed()
        stored = SiteSldResponse.model_validate((await client.get(f"/api/sites/{site.site_id}/sld")).json())
        assert stored.revision == 2
        assert stored.sld.connections == ()
