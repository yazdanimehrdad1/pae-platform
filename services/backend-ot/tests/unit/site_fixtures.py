"""Shared unit-test builders for a site, its devices and their points (no I/O)."""

from datetime import UTC, datetime

from schemas.api_models import (
    DevicePointResponse,
    DevicePointsCategoryGrouped,
    DeviceWithPoints,
    Location,
    SiteResponse,
)
from schemas.internal_models import PointReading

SITE_ID = 1001
CREATED = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def make_site(profile: str | None = "alpha_solar") -> SiteResponse:
    return SiteResponse(
        site_id=SITE_ID,
        client_id="c",
        name="Site",
        location=Location(street="1 Main St", city="Fresno", state="CA", zip_code=93701),
        operator="op",
        capacity="1MW",
        device_count=1,
        profile=profile,
        created_at=CREATED,
        updated_at=CREATED,
        last_update=CREATED,
    )


def make_point(point_id: int, device_id: int, name: str) -> DevicePointResponse:
    return DevicePointResponse(
        id=point_id, site_id=SITE_ID, device_id=device_id, name=name, address=point_id, size=1, data_type="uint16"
    )


def make_device(device_id: int, points: list[DevicePointResponse], device_type: str = "BESS") -> DeviceWithPoints:
    return DeviceWithPoints(
        device_id=device_id,
        site_id=SITE_ID,
        name=f"device_{device_id}",
        type=device_type,
        protocol="modbus",
        host="10.0.0.1",
        port=502,
        server_address=1,
        created_at=CREATED,
        updated_at=CREATED,
        points=DevicePointsCategoryGrouped(native=points),
    )


def make_reading(
    point_id: int,
    value: float | None,
    unit: str | None = None,
    enum_detail: dict[str, str] | None = None,
    name: str = "point",
) -> PointReading:
    return PointReading(
        device_point_id=point_id,
        register_address=point_id,
        name=name,
        data_type="uint16",
        size=1,
        unit=unit,
        enum_detail=enum_detail,
        timestamp=None if value is None else CREATED,
        derived_value=value,
    )
