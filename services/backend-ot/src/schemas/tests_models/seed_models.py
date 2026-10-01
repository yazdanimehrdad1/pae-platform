"""
Models for the development seed data in `tests/seed_db/`.

TEST-ONLY: used by the seeder and its mock data. App code must never import
`schemas.tests_models`.
"""

from pydantic import BaseModel, Field

from schemas.api_models.alarms import AlarmDefinitionCreateRequest
from schemas.api_models.requests import DeviceCreateRequest, VirtualPointCreateRequest


class SeedDevice(BaseModel):
    """A device to seed, tied to its site by name (resolved to site_id at seed time)."""

    site_name: str = Field(..., min_length=1)
    device: DeviceCreateRequest


class SeedVirtualPoint(BaseModel):
    """A virtual point to seed on a device (by name); its inputs are resolved to point IDs first."""

    device_name: str = Field(..., min_length=1)
    point: VirtualPointCreateRequest


class SeedAlarm(BaseModel):
    """A user alarm to seed on a site (by name); its point/device ids are resolved first."""

    site_name: str = Field(..., min_length=1)
    alarm: AlarmDefinitionCreateRequest
