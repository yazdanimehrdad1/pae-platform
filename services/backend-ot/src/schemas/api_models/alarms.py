"""System alarms: definitions (what an alarm checks) and their API bodies.

An alarm belongs to a site and comes from one of two sources:

- ``USER``: built in the UI. Its ``rule`` is one of three kinds:
  - ``threshold``: one comparison (a point against a value or another point, or a bit test), raised
    after ``delay_sec`` of continuous violation, cleared past the limit by ``deadband``;
  - ``comms_stale``: a device with no successful poll for ``stale_after_sec``;
  - ``condition``: ALL/ANY groups of comparisons over several points, raised after ``delay_sec``.
- ``PROFILE``: declared in the site profile's code (site_profiles); its logic, name, severity and
  message are code. Users can only enable it, set its notifications and pick it for Active alarms.

Comparisons and groups are the virtual-point models (``VirtualCondition``, ``VirtualConditionGroup``),
so both features validate and evaluate them the same way.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.api_models.virtual_points import (
    BIT_OPERATORS,
    MAX_GROUP_DEPTH,
    VirtualCondition,
    VirtualConditionGroup,
)

AlarmSeverity = Literal["fault", "warning"]
AlarmSource = Literal["USER", "PROFILE"]
AlarmKind = Literal["threshold", "comms_stale", "condition", "profile"]

# How many alarms a site can have enabled. An enabled alarm is evaluated and shown in Active alarms;
# a disabled one is neither.
MAX_ENABLED_ALARMS = 20
ALARM_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"
ALARM_NAME_MAX_LENGTH = 150


class ThresholdAlarm(BaseModel):
    """One comparison: `point <op> value`, `point <op> other point`, or a bit test."""

    kind: Literal["threshold"]
    condition: VirtualCondition
    delay_sec: int = Field(0, ge=0, description="The condition must hold this long before the alarm raises")
    deadband: float = Field(
        0.0,
        ge=0,
        description="Clear hysteresis: the value must come back past the limit by this much. For a "
        "point-vs-point comparison it applies to the other point's value. Not used by bit tests.",
    )

    @model_validator(mode="after")
    def _no_deadband_on_bit_tests(self) -> ThresholdAlarm:
        if self.condition.operator in BIT_OPERATORS and self.deadband != 0:
            raise ValueError(f"operator '{self.condition.operator}' takes no deadband")
        return self


class CommsStaleAlarm(BaseModel):
    """A device with no successful poll for more than `stale_after_sec`."""

    kind: Literal["comms_stale"]
    device_id: int
    stale_after_sec: int = Field(..., ge=1)


class ConditionAlarm(BaseModel):
    """ALL/ANY groups of comparisons over several points; clears as soon as the group no longer holds."""

    kind: Literal["condition"]
    when: VirtualConditionGroup
    delay_sec: int = Field(0, ge=0, description="The group must hold this long before the alarm raises")

    @model_validator(mode="after")
    def _check_depth(self) -> ConditionAlarm:
        if self.when.depth() > MAX_GROUP_DEPTH:
            raise ValueError(f"groups nest at most {MAX_GROUP_DEPTH} levels deep")
        return self


UserAlarmRule = ThresholdAlarm | CommsStaleAlarm | ConditionAlarm
AlarmRule = Annotated[UserAlarmRule, Field(discriminator="kind")]

AlarmName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=ALARM_NAME_MAX_LENGTH,
        pattern=ALARM_NAME_PATTERN,
        description="Identifier: letters, digits and underscore, not starting with a digit; unique per site ignoring case",
    ),
]


class AlarmDefinitionCreateRequest(BaseModel):
    """A new USER alarm. (PROFILE alarms come from code, never from this route.)"""

    name: AlarmName
    severity: AlarmSeverity
    message: str = Field("", max_length=500, description="Shown in the alarm list and event log")
    enabled: bool = Field(True, description=f"Evaluated and shown in Active alarms (at most {MAX_ENABLED_ALARMS} enabled per site)")
    notify_mobile: bool = False
    notify_email: bool = False
    rule: AlarmRule


class AlarmDefinitionUpdateRequest(BaseModel):
    """Fields to change; omitted ones keep their value. A PROFILE alarm accepts only
    enabled, notify_mobile and notify_email."""

    model_config = ConfigDict(extra="forbid")

    name: AlarmName | None = None
    severity: AlarmSeverity | None = None
    message: str | None = Field(None, max_length=500)
    enabled: bool | None = None
    notify_mobile: bool | None = None
    notify_email: bool | None = None
    rule: AlarmRule | None = None


# Fields a user may change on a PROFILE alarm (the rest is code).
PROFILE_EDITABLE_FIELDS = frozenset({"enabled", "notify_mobile", "notify_email"})


class AlarmDefinitionResponse(BaseModel):
    """One alarm of a site."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    source: AlarmSource
    profile_alarm_key: str | None = Field(None, description="PROFILE only: the alarm's key in the site profile")
    name: str
    kind: AlarmKind
    rule: AlarmRule | None = Field(None, description="USER only: what the alarm checks")
    severity: AlarmSeverity
    message: str
    enabled: bool
    notify_mobile: bool
    notify_email: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


# --- Events and the page snapshot -----------------------------------------------------------

# Cleared alarms stay in the snapshot (and its log) this long, like the UI's "cleared in last 6 h".
RECENT_WINDOW_HOURS = 6


class AlarmEventResponse(BaseModel):
    """One raise of an alarm and its clear (cleared_at None while active)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    definition_id: int
    site_id: int
    device_id: int | None = Field(None, description="The device the alarm is about; None for a site-level alarm")
    severity: AlarmSeverity
    raised_at: datetime
    cleared_at: datetime | None = None
    value_at_raise: float | None = None
    message: str


class AlarmLogEntry(BaseModel):
    """One line of the event log: a raise or a clear."""

    id: str = Field(..., description="'<event id>:raised' or '<event id>:cleared'")
    event_id: int
    definition_id: int
    device_id: int | None = None
    kind: Literal["raised", "cleared"]
    severity: AlarmSeverity
    at: datetime
    message: str


class AlarmSnapshotResponse(BaseModel):
    """Everything the alarms page shows for "now"."""

    site_id: int
    now: datetime = Field(..., description="Server time; durations are measured against it")
    definitions: list[AlarmDefinitionResponse]
    events: list[AlarmEventResponse] = Field(
        ..., description=f"Active events plus those cleared within the last {RECENT_WINDOW_HOURS} h, newest raise first"
    )
    log: list[AlarmLogEntry] = Field(
        ..., description=f"Raises and clears within the last {RECENT_WINDOW_HOURS} h, newest first"
    )
