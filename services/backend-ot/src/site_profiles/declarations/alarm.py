"""
The standard shape of an alarm a site profile declares in code (a PROFILE alarm).

A profile lists its alarms next to its endpoints:

    SiteAlarm(
        key="placeholder_profile_alarm_1",    # stable id; the alarm row is found by it
        name="placeholder_profile_alarm_1",   # identifier shown in the UI (like a rule name)
        severity="fault",
        message="PLACEHOLDER profile alarm 1: inverter_state is not mppt or derating",
        evaluate=placeholder_profile_alarm_1, # async (AlarmContext) -> AlarmCheck
    )

Each site whose profile declares it gets one alarm_definitions row (source PROFILE). Its logic,
name, severity and message come from here and are read-only in the UI; users can enable it, set
its notifications and pick it for Active alarms. The evaluation job calls `evaluate` every cycle
and raises/clears the alarm from `AlarmCheck.active`.
"""

import inspect
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.api_models.alarms import ALARM_NAME_MAX_LENGTH, ALARM_NAME_PATTERN, AlarmSeverity
from schemas.site_profiles import AlarmCheck, AlarmContext

__all__ = ["AlarmCheck", "AlarmContext", "AlarmEvaluator", "SiteAlarm"]

AlarmEvaluator = Callable[[AlarmContext], Awaitable[AlarmCheck]]
"""The standard check signature: async def <name>(ctx: AlarmContext) -> AlarmCheck."""


class SiteAlarm(BaseModel):
    """One alarm a site profile declares. Declared in site_profiles/.../profile.py."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-z0-9]+(_[a-z0-9]+)*$",
        description="Stable id, lower-case words joined by '_'; renaming it makes a new alarm",
    )
    name: str = Field(..., min_length=1, max_length=ALARM_NAME_MAX_LENGTH, pattern=ALARM_NAME_PATTERN)
    severity: AlarmSeverity
    message: str = Field(..., min_length=1, max_length=500)
    evaluate: AlarmEvaluator = Field(..., description="The async check run every evaluation cycle")

    @field_validator("evaluate")
    @classmethod
    def _evaluate_is_async(cls, evaluate: AlarmEvaluator) -> AlarmEvaluator:
        if not inspect.iscoroutinefunction(evaluate):
            raise ValueError(f"evaluate {evaluate!r} must be an 'async def' function")
        return evaluate
