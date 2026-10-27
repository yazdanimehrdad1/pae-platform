"""
The standard shape of a virtual point a site profile declares in code (a profile virtual point).

A profile lists its virtual points next to its alarms:

    SiteVirtualPoint(
        key="poi_active_power",            # stable id; the point row is found by it
        device_name="poi-meter",           # the site's device the point lives on
        point_name="poi_active_power",     # the point's name (adopts a VIRTUAL point of that name)
        unit="kW",
        description="Sum of the feeder meters' active power",  # shown in place of a formula
        compute=poi_active_power,          # async (VirtualPointContext) -> list[TimestampedValue]
    )

Each site whose profile declares it gets one VIRTUAL device point (helpers.profile_points.sync).
Unlike a point built in the UI, its values are stored: the job profile_point_compute calls
`compute` every poll interval for the window after the last one it stored, and stores what it
returns in device_points_readings. `compute` returns one value per input poll timestamp in the
window, so the stored values line up with the readings they came from.
"""

import inspect
from collections.abc import Awaitable, Callable
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.internal_models import TimestampedValue
from schemas.site_profiles import VirtualPointContext

__all__ = ["SiteVirtualPoint", "TimestampedValue", "VirtualPointCompute", "VirtualPointContext"]

VirtualPointCompute = Callable[[VirtualPointContext], Awaitable[list[TimestampedValue]]]
"""The standard signature: async def <name>(ctx: VirtualPointContext) -> list[TimestampedValue]."""


class SiteVirtualPoint(BaseModel):
    """One stored virtual point a site profile declares. Declared in site_profiles/.../profile.py."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-z0-9]+(_[a-z0-9]+)*$",
        description="Stable id, lower-case words joined by '_'; renaming it makes a new point",
    )
    device_name: str = Field(..., min_length=1, description="The name of the site's device the point lives on")
    point_name: str = Field(..., min_length=1, max_length=255)
    unit: str | None = Field(None, max_length=50)
    description: str = Field(
        ..., min_length=1, max_length=500,
        description="What `compute` calculates, from which points; shown to users in place of a formula",
    )
    compute: VirtualPointCompute = Field(..., description="The async function run every compute cycle")
    backfill: timedelta = Field(
        timedelta(0), ge=timedelta(0), description="How far back the first run computes, from when it runs"
    )

    @field_validator("compute")
    @classmethod
    def _compute_is_async(cls, compute: VirtualPointCompute) -> VirtualPointCompute:
        if not inspect.iscoroutinefunction(compute):
            raise ValueError(f"compute {compute!r} must be an 'async def' function")
        return compute
