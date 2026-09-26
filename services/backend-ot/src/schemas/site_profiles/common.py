"""
Models shared by every site profile: the query window all site functions accept, the
per-request SiteContext, the discovery response, and the results of the common functions.
"""

from datetime import datetime
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from helpers.common.date_time import (
    TimeRange,
    normalize_to_utc,
    resolve_time_range,
    resolve_timezone,
)
from schemas.api_models import DevicePointResponse, DeviceWithPoints, SiteResponse

FunctionKind = Literal["common", "site", "device"]


# --- Query window ------------------------------------------------------------------------


class TimeWindow(BaseModel):
    """A resolved query window: aware UTC bounds plus the zone to render results in."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    start_time: datetime
    end_time: datetime
    display_tz: ZoneInfo | None = None

    def display(self, value: datetime) -> datetime:
        """Render an aware UTC datetime in the requested zone (same instant)."""
        return value if self.display_tz is None else value.astimezone(self.display_tz)


class TimeWindowParams(BaseModel):
    """
    Query parameters every site function accepts. A function that needs more parameters
    subclasses this and adds flat (query-string) fields.

    Pick one window: `time_range` (relative to now), or `start_time` with an optional
    `end_time` (defaults to now). Bounds follow the same timezone rules as the
    device-point-readings endpoints.
    """

    start_time: datetime | None = Field(
        None,
        description="Window start (ISO 8601 with a UTC offset, or naive with tz). Cannot be combined with time_range.",
    )
    end_time: datetime | None = Field(
        None,
        description="Window end; defaults to now. Needs start_time. Cannot be combined with time_range.",
    )
    time_range: TimeRange | None = Field(
        None, description="Relative window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M."
    )
    tz: str | None = Field(
        None,
        description="IANA timezone (or US shorthand such as 'PT') for naive bounds and for response timestamps.",
    )

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        if self.time_range is not None and (self.start_time or self.end_time):
            raise ValueError("Use either time_range or start_time/end_time, not both")
        if self.time_range is None and self.start_time is None:
            raise ValueError("Provide time_range, or start_time (with an optional end_time)")
        display_tz = resolve_timezone(self.tz) if self.tz else None
        if self.start_time is not None:
            start = normalize_to_utc(self.start_time, "start_time", display_tz)
            if self.end_time is not None:
                end = normalize_to_utc(self.end_time, "end_time", display_tz)
                if start >= end:
                    raise ValueError("start_time must be before end_time")
        return self

    def resolve_window(self) -> TimeWindow:
        """Resolve to aware UTC bounds. Reads the clock for time_range and a missing end_time."""
        display_tz = resolve_timezone(self.tz) if self.tz else None
        if self.time_range is not None:
            start, end = resolve_time_range(self.time_range)
            return TimeWindow(start_time=start, end_time=end, display_tz=display_tz)
        if self.start_time is None:  # unreachable: _check_window requires one of the two
            raise ValueError("Provide time_range, or start_time (with an optional end_time)")
        start = normalize_to_utc(self.start_time, "start_time", display_tz)
        end = (
            normalize_to_utc(self.end_time, "end_time", display_tz)
            if self.end_time is not None
            else datetime.now(start.tzinfo)
        )
        return TimeWindow(start_time=start, end_time=end, display_tz=display_tz)


# --- Per-request context -----------------------------------------------------------------


class SiteContext(BaseModel):
    """What a site function gets to work with: the site, its devices and their points."""

    site: SiteResponse
    devices: list[DeviceWithPoints]
    device: DeviceWithPoints | None = Field(None, description="The target device for device-level calls")

    def points_named(
        self, name: str, devices: list[DeviceWithPoints] | None = None
    ) -> list[DevicePointResponse]:
        """Every point called `name` on the given devices (default: all the site's devices)."""
        return [
            point
            for device in (self.devices if devices is None else devices)
            for point in (
                device.points.standardized + device.points.native + device.points.virtual
            )
            if point.name == name
        ]


# --- Discovery (GET /site-functions/site/{site_id}) --------------------------------------


class SiteEndpointInfo(BaseModel):
    name: str = Field(..., description="Function name, the last URL segment; starts with its kind")
    kind: FunctionKind = Field(
        ...,
        description="common/site: /site/{site_id}/{name}; device: /site/{site_id}/device/{device_id}/{name}",
    )
    method: Literal["GET"]
    summary: str


class SiteEndpointsResponse(BaseModel):
    site_id: int
    profile: str = Field(..., description="The site's profile key")
    endpoints: list[SiteEndpointInfo] = Field(default_factory=list, description="Endpoints declared in the site's profile.py")


# --- common: energy-summary --------------------------------------------------------------


class DeviceEnergy(BaseModel):
    device_id: int
    device_name: str
    point_id: int = Field(..., description="The power point that was integrated")
    sample_count: int
    energy_kwh: float


class EnergySummaryResult(BaseModel):
    site_id: int
    start_time: datetime
    end_time: datetime
    energy_kwh: float = Field(..., description="Sum over devices")
    devices: list[DeviceEnergy] = Field(default_factory=list)
