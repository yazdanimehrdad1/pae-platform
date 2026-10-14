"""
When a schedule generates its template's report (its cadence), and the schedule API models.

A cadence is in the site's time zone ("every day at 06:00" is 06:00 on the site's clock, DST
included). Kept apart from api.py because the ORM's column types import the cadence model, and
api.py imports schemas.site_profiles, which imports the ORM.
"""

import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.reports.definition import ReportWindow

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

MAX_KEEP_LAST = 1000
MAX_KEEP_DAYS = 3650


class _Cadence(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _AtTime(_Cadence):
    time: str = Field(..., description="HH:MM on the site's clock (24 h)")

    @field_validator("time")
    @classmethod
    def _check_time(cls, time: str) -> str:
        if not TIME_PATTERN.match(time):
            raise ValueError("time must be HH:MM, 00:00 to 23:59")
        return time


class HourlyCadence(_Cadence):
    """Every hour, at this minute."""

    kind: Literal["hourly"]
    minute: int = Field(0, ge=0, le=59)


class DailyCadence(_AtTime):
    kind: Literal["daily"]


class WeeklyCadence(_AtTime):
    """On these weekdays (0 = Monday ... 6 = Sunday)."""

    kind: Literal["weekly"]
    weekdays: list[int] = Field(..., min_length=1, max_length=7)

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, weekdays: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in weekdays) or len(set(weekdays)) != len(weekdays):
            raise ValueError("weekdays are 0 (Monday) to 6 (Sunday), each at most once")
        return sorted(weekdays)


class MonthlyCadence(_AtTime):
    """On this day of every month (1 to 28, so every month has it)."""

    kind: Literal["monthly"]
    day_of_month: int = Field(..., ge=1, le=28)


ReportCadence = Annotated[HourlyCadence | DailyCadence | WeeklyCadence | MonthlyCadence, Field(discriminator="kind")]


class ReportScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: int
    cadence: ReportCadence
    window_override: ReportWindow | None = Field(None, description="Replaces the template's window for these reports; null keeps it")
    enabled: bool = True
    keep_last: int | None = Field(None, ge=1, le=MAX_KEEP_LAST, description="Keep at most this many of its reports (newest); null keeps all")
    keep_days: int | None = Field(None, ge=1, le=MAX_KEEP_DAYS, description="Delete its reports older than this many days; null keeps them")


class ReportScheduleUpdateRequest(BaseModel):
    """Omitted fields keep their value; window_override, keep_last and keep_days take an explicit
    null to clear them."""

    model_config = ConfigDict(extra="forbid")

    cadence: ReportCadence | None = None
    window_override: ReportWindow | None = None
    enabled: bool | None = None
    keep_last: int | None = Field(None, ge=1, le=MAX_KEEP_LAST)
    keep_days: int | None = Field(None, ge=1, le=MAX_KEEP_DAYS)

    @model_validator(mode="after")
    def _enabled_not_null(self) -> Self:
        if "enabled" in self.model_fields_set and self.enabled is None:
            raise ValueError("enabled can't be null")
        if "cadence" in self.model_fields_set and self.cadence is None:
            raise ValueError("cadence can't be null")
        return self
