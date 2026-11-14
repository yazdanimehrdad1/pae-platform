"""Models the reports module passes between its parts (never sent over the API)."""

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.api_models import DevicePointResponse, DeviceWithPoints, SiteResponse
from schemas.reports.api import ReportAlarm, ReportSiteFunction
from schemas.reports.definition import PointStat, ReportDefinition, ReportWindow
from schemas.reports.schedules import ReportCadence


class ReportSiteContext(BaseModel):
    """What a report is checked and generated against: the site, its active devices and points,
    the site functions its profile offers, and its live alarms."""

    site: SiteResponse
    devices: list[DeviceWithPoints] = Field(default_factory=list)
    functions: list[ReportSiteFunction] = Field(default_factory=list)
    alarms: list[ReportAlarm] = Field(default_factory=list)

    def find_point(self, point_id: int) -> tuple[DevicePointResponse, DeviceWithPoints] | None:
        for device in self.devices:
            for point in device.points.standardized + device.points.native + device.points.virtual:
                if point.id == point_id:
                    return point, device
        return None

    def find_device(self, device_id: int) -> DeviceWithPoints | None:
        return next((device for device in self.devices if device.device_id == device_id), None)

    def find_function(self, name: str) -> ReportSiteFunction | None:
        return next((function for function in self.functions if function.name == name), None)

    def find_alarm(self, alarm_id: int) -> ReportAlarm | None:
        return next((alarm for alarm in self.alarms if alarm.id == alarm_id), None)


class DueSchedule(BaseModel):
    """A schedule whose time has come, with the template it generates."""

    schedule_id: int
    site_id: int
    template_id: int
    template_name: str
    template_version: int
    definition: ReportDefinition = Field(..., description="The template's definition, with the schedule's window if it overrides it")
    cadence: ReportCadence
    keep_last: int | None = None
    keep_days: int | None = None
    due_at: datetime = Field(..., description="The occurrence being generated (the schedule's next_run_at)")


class ScheduleFields(BaseModel):
    """A schedule's stored fields, as the service worked them out (next_run_at included)."""

    template_id: int
    cadence: ReportCadence
    window_override: ReportWindow | None = None
    enabled: bool
    keep_last: int | None = None
    keep_days: int | None = None
    next_run_at: datetime | None = None


class PointStatValues(BaseModel):
    """The statistics of one point over the window, or over one hour/day bucket of it."""

    point_id: int
    bucket_start: datetime | None = Field(None, description="Start of the bucket (UTC); None for the whole window")
    values: dict[PointStat, float | None] = Field(default_factory=dict)
