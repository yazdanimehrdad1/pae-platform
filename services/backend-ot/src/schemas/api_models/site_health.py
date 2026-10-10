"""Site health (GET /api/sites/{site_id}/health): which ALARM-class points are set, per device.

A point is set when its latest reading is non-zero. A point that has never reported is unknown,
not set, and is counted on its own so a silent device doesn't read as healthy.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.api_models.types import Severity


class ActivePointAlarm(BaseModel):
    """An ALARM-class point whose latest reading is set."""

    device_point_id: int
    device_point_name: str = Field(..., description="The point's name, for display")
    severity: Severity | None = Field(None, description="The point's severity; null if the point declares none")
    value: float = Field(..., description="The latest derived value (non-zero)")
    active_bits: list[str] = Field(
        default_factory=list, description="Bitfield points: the named bits that are 1, in bit order"
    )
    enum_label: str | None = Field(None, description="Enum points: the label of the current value")
    timestamp: datetime = Field(..., description="When the latest reading was stored")


class AlarmCounts(BaseModel):
    """How many evaluated ALARM points are set, per severity, and how many have never reported."""

    highest_severity: Severity | None = Field(None, description="The highest severity that is set; null if none is")
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    unknown_count: int = Field(0, description="ALARM points that have never reported a reading")


class DeviceAlarmStatus(AlarmCounts):
    """One device's set ALARM points."""

    device_id: int
    device_name: str
    active_alarms: list[ActivePointAlarm] = Field(default_factory=list)


class SiteHealthResponse(AlarmCounts):
    """The site's set ALARM points, per device, rolled up to the site."""

    site_id: int
    generated_at: datetime
    severity_filter: list[Severity] | None = Field(
        None, description="The severities evaluated; null means all (including points without a severity)"
    )
    device_ids_filter: list[int] | None = Field(None, description="The devices evaluated; null means all of the site's")
    devices: list[DeviceAlarmStatus] = Field(default_factory=list)
