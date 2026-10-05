"""
Models for the development seed data in `tests/seed_db/`.

TEST-ONLY: used by the seeder and its mock data. App code must never import
`schemas.tests_models`.
"""

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from schemas.api_models.alarms import AlarmDefinitionCreateRequest
from schemas.api_models.requests import (
    DeviceCreateRequest,
    DevicePointCreateRequest,
    SiteCreateRequest,
    VirtualPointCreateRequest,
)
from schemas.api_models.single_line_diagram import SiteSld

# Resolve a seeded point / device to its id once the rows exist: (device_name, point_name) -> id,
# device_name -> id. The hand-written parts of a seed are functions of these.
PointIdResolver = Callable[[str, str], int]
DeviceIdResolver = Callable[[str], int]


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


def _no_virtual_points(_point_id: PointIdResolver) -> list[SeedVirtualPoint]:
    return []


def _no_alarms(_point_id: PointIdResolver, _device_id: DeviceIdResolver) -> list[SeedAlarm]:
    return []


def _no_slds(_point_id: PointIdResolver, _device_id: DeviceIdResolver) -> dict[str, SiteSld]:
    return {}


class SeedData(BaseModel):
    """One seed: its sites, devices (with their NATIVE points, keyed by device name), and the
    parts that reference ids, built once those exist (virtual points, user alarms, SLDs)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    sites: list[SiteCreateRequest]
    devices: list[SeedDevice]
    device_points: dict[str, list[DevicePointCreateRequest]]
    virtual_points: Callable[[PointIdResolver], list[SeedVirtualPoint]] = _no_virtual_points
    user_alarms: Callable[[PointIdResolver, DeviceIdResolver], list[SeedAlarm]] = _no_alarms
    site_slds: Callable[[PointIdResolver, DeviceIdResolver], dict[str, SiteSld]] = _no_slds
