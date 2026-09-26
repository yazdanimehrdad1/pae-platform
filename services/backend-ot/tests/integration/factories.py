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
)

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

# METER has no standardized-point templates, so a new device starts with no points.
_DEVICE_DEFAULTS = DeviceCreateRequest(
    name="meter-1", type="METER", host="10.0.0.10", port=502, read_from_aggregator=False
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
