"""The alarm engine: what one evaluation of one alarm decides. Pure: no I/O, no clock.

A port of the UI's reference engine (web-plusdas `features/alarms/lib/ruleEngine.ts`), applied to
one observation per cycle instead of a replayed series:

- an alarm raises after its condition has held continuously for `delay_sec` (0 = at once), at
  the evaluation that completes the delay;
- an active alarm clears when its clear test passes: a threshold comparison must come back past
  the limit by `deadband` (hysteresis); `==`, `!=`, bit tests, conditions and profile checks clear
  as soon as they no longer hold;
- comms-stale raises back-dated to last success + timeout, and clears on the next fresh poll;
- an evaluation without data (an input missing or stale) changes nothing, but resets the delay
  timer, so the condition must hold across fresh data.

Comparisons and groups use the virtual-point evaluators (`condition_holds`, `group_holds`).
"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from helpers.virtual_points.definition import condition_point_ids
from helpers.virtual_points.evaluate import condition_holds, group_holds
from schemas.api_models.alarms import CommsStaleAlarm, ConditionAlarm, ThresholdAlarm
from schemas.api_models.virtual_points import BIT_OPERATORS, VirtualCondition


class AlarmObservation(BaseModel):
    """What one evaluation saw for one alarm."""

    holds: bool = Field(..., description="The raise condition holds")
    cleared: bool = Field(..., description="The clear test passes (only used while active)")
    value: float | None = Field(None, description="The watched value, recorded when it raises")
    device_id: int | None = None
    raise_at: datetime | None = Field(None, description="Back-dated raise time (comms-stale); default: now")


class AlarmState(BaseModel):
    active: bool = False
    condition_since: datetime | None = None


class AlarmTransition(BaseModel):
    kind: Literal["raise", "clear"]
    at: datetime
    value: float | None = None
    device_id: int | None = None


def step(
    state: AlarmState, observation: AlarmObservation | None, delay: timedelta, now: datetime
) -> tuple[AlarmState, AlarmTransition | None]:
    """The next state and, if any, the raise or clear this evaluation causes."""
    if observation is None:
        return AlarmState(active=state.active), None
    if state.active:
        if observation.cleared:
            return AlarmState(), AlarmTransition(kind="clear", at=now)
        return state, None
    if not observation.holds:
        return AlarmState(), None
    since = state.condition_since or now
    if now - since >= delay:
        at = observation.raise_at or now
        return AlarmState(active=True), AlarmTransition(kind="raise", at=at, value=observation.value, device_id=observation.device_id)
    return AlarmState(condition_since=since), None


def disabled_step(state: AlarmState, now: datetime) -> tuple[AlarmState, AlarmTransition | None]:
    """A disabled alarm raises nothing and clears an active one."""
    return AlarmState(), (AlarmTransition(kind="clear", at=now) if state.active else None)


def threshold_cleared(condition: VirtualCondition, values: Mapping[int, float], deadband: float) -> bool:
    """The clear test with hysteresis: `>`/`>=` clear below limit - deadband, `<`/`<=` above limit +
    deadband (the limit is the value or the other point); others clear when the condition is false."""
    if condition.operator in BIT_OPERATORS or condition.operator in ("==", "!="):
        return not condition_holds(condition, values)
    value = values[condition.point_id]
    limit = values[condition.compare_point_id] if condition.compare_point_id is not None else condition.value
    assert limit is not None  # guaranteed by VirtualCondition's validator
    if condition.operator in (">", ">="):
        return value < limit - deadband
    return value > limit + deadband


def observe_threshold(rule: ThresholdAlarm, values: Mapping[int, float | None], device_of: Mapping[int, int]) -> AlarmObservation | None:
    """None when a point it reads has no fresh value."""
    known = _known(condition_point_ids(rule.condition), values)
    if known is None:
        return None
    return AlarmObservation(
        holds=condition_holds(rule.condition, known),
        cleared=threshold_cleared(rule.condition, known, rule.deadband),
        value=known[rule.condition.point_id],
        device_id=device_of.get(rule.condition.point_id),
    )


def observe_condition(rule: ConditionAlarm, values: Mapping[int, float | None], device_of: Mapping[int, int]) -> AlarmObservation | None:
    """None when a point it reads has no fresh value. The device is the points' one, if they share one."""
    point_ids = condition_point_ids(rule.when)
    known = _known(point_ids, values)
    if known is None:
        return None
    holds = group_holds(rule.when, known)
    devices = {device_of.get(point_id) for point_id in point_ids}
    return AlarmObservation(holds=holds, cleared=not holds, device_id=devices.pop() if len(devices) == 1 else None)


def observe_comms_stale(rule: CommsStaleAlarm, last_success: datetime | None, now: datetime) -> AlarmObservation | None:
    """No successful poll for longer than the timeout. None before the device's first success."""
    if last_success is None:
        return None
    timeout = timedelta(seconds=rule.stale_after_sec)
    stale = now - last_success > timeout
    return AlarmObservation(holds=stale, cleared=not stale, device_id=rule.device_id, raise_at=last_success + timeout)


def _known(point_ids: set[int], values: Mapping[int, float | None]) -> dict[int, float] | None:
    known: dict[int, float] = {}
    for point_id in point_ids:
        value = values.get(point_id)
        if value is None:
            return None
        known[point_id] = value
    return known
