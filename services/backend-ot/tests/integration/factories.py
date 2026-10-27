"""
Request builders and create-via-API helpers shared by integration tests.

Tests arrange state through the public API wherever possible, so they exercise the same
write path a real client does. Only data the API can't create (readings) goes in via SQL.

Builders return the app's own request models (validated at build time), and the create
helpers return the app's response models, so tests assert on typed attributes.
"""

from datetime import datetime

import asyncpg
from httpx import AsyncClient
from pydantic import TypeAdapter

from schemas.api_models import (
    Coordinates,
    DeviceCreateRequest,
    DevicePointCreateRequest,
    DevicePointResponse,
    DevicePointsBulkRequest,
    DeviceWithPoints,
    Location,
    SiteCreateRequest,
    SiteResponse,
    StandardizedPointLinkRequest,
    VirtualPointCreateRequest,
)
from schemas.api_models.alarms import AlarmDefinitionCreateRequest, AlarmDefinitionResponse
from schemas.tests_models import LinkedBess

DEVICE_POINT_LIST = TypeAdapter(list[DevicePointResponse])

_SITE_DEFAULTS = SiteCreateRequest(
    client_id="client-1",
    name="Test Site",
    location=Location(street="1 Main St", city="Fresno", state="CA", zip_code=93701),
    operator="Test Operator",
    capacity="10 MW",
    description="integration test site",
    coordinates=Coordinates(lat=36.74, lng=-119.78),
)

# RTAC has no standardized-point templates, so a new device starts with no points.
_DEVICE_DEFAULTS = DeviceCreateRequest(
    name="rtac-1", type="RTAC", host="10.0.0.10", port=502, read_from_aggregator=False
)

_POINT_DEFAULTS = DevicePointCreateRequest(
    name="active_power", poll_kind="holding", address=100, size=2, data_type="float32", unit="kW"
)


def site_request(**overrides: object) -> SiteCreateRequest:
    return SiteCreateRequest.model_validate(_SITE_DEFAULTS.model_dump() | overrides)


def device_request(**overrides: object) -> DeviceCreateRequest:
    return DeviceCreateRequest.model_validate(_DEVICE_DEFAULTS.model_dump() | overrides)


def point_request(**overrides: object) -> DevicePointCreateRequest:
    return DevicePointCreateRequest.model_validate(_POINT_DEFAULTS.model_dump() | overrides)


async def create_site(client: AsyncClient, **overrides: object) -> SiteResponse:
    response = await client.post(
        "/api/sites", json=site_request(**overrides).model_dump(mode="json")
    )
    assert response.status_code == 201, response.text
    return SiteResponse.model_validate(response.json())


async def create_device(client: AsyncClient, site_id: int, **overrides: object) -> DeviceWithPoints:
    response = await client.post(
        f"/api/devices/site/{site_id}/devices",
        json=device_request(**overrides).model_dump(mode="json"),
    )
    assert response.status_code == 201, response.text
    return DeviceWithPoints.model_validate(response.json())


async def upsert_points(
    client: AsyncClient, site_id: int, device_id: int, points: list[DevicePointCreateRequest]
) -> list[DevicePointResponse]:
    body = DevicePointsBulkRequest(points=points)
    response = await client.put(
        f"/api/device-points/site/{site_id}/device/{device_id}/bulk",
        json=body.model_dump(mode="json", by_alias=True),  # wire names, e.g. "class"
    )
    assert response.status_code == 200, response.text
    return DEVICE_POINT_LIST.validate_python(response.json())


async def insert_reading(
    db: asyncpg.Connection,
    point: DevicePointResponse,
    timestamp: datetime,
    raw_value: float | None,
    derived_value: float | None,
) -> None:
    await db.execute(
        """
        INSERT INTO device_points_readings
            ("timestamp", site_id, device_id, device_point_id, raw_value, derived_value)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        timestamp,
        point.site_id,
        point.device_id,
        point.id,
        raw_value,
        derived_value,
    )


async def insert_readings(
    db: asyncpg.Connection, point: DevicePointResponse, samples: list[tuple[datetime, float | None]]
) -> None:
    """Many readings of one point at once (COPY), raw value = derived value; for dense windows."""
    await db.copy_records_to_table(
        "device_points_readings",
        columns=["timestamp", "site_id", "device_id", "device_point_id", "raw_value", "derived_value"],
        records=[(time, point.site_id, point.device_id, point.id, value, value) for time, value in samples],
    )


async def create_virtual_point(
    client: AsyncClient, site_id: int, device_id: int, request: VirtualPointCreateRequest
) -> DevicePointResponse:
    response = await client.post(
        f"/api/device-points/site/{site_id}/device/{device_id}/virtual",
        json=request.model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 201, response.text
    return DevicePointResponse.model_validate(response.json())


async def create_alarm(
    client: AsyncClient, site_id: int, request: AlarmDefinitionCreateRequest
) -> AlarmDefinitionResponse:
    response = await client.post(
        f"/api/alarms/site/{site_id}/definitions", json=request.model_dump(mode="json")
    )
    assert response.status_code == 201, response.text
    return AlarmDefinitionResponse.model_validate(response.json())



def link_url(site_id: int, device_id: int, point_id: int) -> str:
    return f"/api/device-points/site/{site_id}/device/{device_id}/{point_id}/link"


async def link_point(
    client: AsyncClient, point: DevicePointResponse, request: StandardizedPointLinkRequest
) -> DevicePointResponse:
    response = await client.put(
        link_url(point.site_id, point.device_id, point.id), json=request.model_dump(mode="json")
    )
    assert response.status_code == 200, response.text
    return DevicePointResponse.model_validate(response.json())


async def standardized_points_by_name(client: AsyncClient, site_id: int, device_id: int) -> dict[str, DevicePointResponse]:
    response = await client.get(
        f"/api/device-points/site/{site_id}/device/{device_id}", params={"category": "STANDARDIZED"}
    )
    assert response.status_code == 200, response.text
    return {point.name: point for point in DEVICE_POINT_LIST.validate_python(response.json())}


async def create_linked_bess(client: AsyncClient, linked: bool = True) -> LinkedBess:
    """A BESS with W (in W) and SoC (in %); unless linked=False, BESS_ACTIVE_POWER is linked to W
    (W -> kW) and BESS_STATE_OF_CHARGE to SoC."""
    site = await create_site(client)
    device = await create_device(client, site.site_id, name="bess-1", type="BESS")
    power, soc = await upsert_points(client, site.site_id, device.device_id, [
        point_request(name="W", address=100, unit="W"),
        point_request(name="SoC", address=110, unit="%"),
    ])
    standardized = await standardized_points_by_name(client, site.site_id, device.device_id)
    active_power, state_of_charge = standardized["BESS_ACTIVE_POWER"], standardized["BESS_STATE_OF_CHARGE"]
    if linked:
        active_power = await link_point(
            client, active_power, StandardizedPointLinkRequest(source_point_id=power.id, unit="kW", scale_factor=0.001)
        )
        state_of_charge = await link_point(
            client, state_of_charge, StandardizedPointLinkRequest(source_point_id=soc.id, unit="%")
        )
    return LinkedBess(
        site_id=site.site_id, device_id=device.device_id, power=power, soc=soc,
        active_power=active_power, state_of_charge=state_of_charge,
    )


# alpha_solar declares the profile virtual point poi_apparent_power (sqrt(P^2 + Q^2)) on this device.
ALPHA_POI_DEVICE = "mock-device-3"


async def create_alpha_poi_device(client: AsyncClient) -> tuple[SiteResponse, DeviceWithPoints, list[DevicePointResponse]]:
    """An alpha_solar site with its POI device and the two NATIVE points poi_apparent_power reads
    (creating the device syncs the profile point onto it)."""
    site = await create_site(client, profile="alpha_solar")
    device = await create_device(client, site.site_id, name=ALPHA_POI_DEVICE)
    points = await upsert_points(client, site.site_id, device.device_id, [
        point_request(name="poi_active_power_total", address=201),
        point_request(name="poi_reactive_power_total", address=203, unit="kvar"),
    ])
    return site, device, points


async def device_points(client: AsyncClient, site_id: int, device_id: int) -> dict[str, DevicePointResponse]:
    response = await client.get(f"/api/device-points/site/{site_id}/device/{device_id}")
    assert response.status_code == 200, response.text
    return {point.name: point for point in DEVICE_POINT_LIST.validate_python(response.json())}
