"""Event scenarios: a stored timeline of condition changes (per site), played by the engine.

Each event fires just before a step is computed:
- `{"kind": "step", "step": N}`: the Nth step after the scenario starts (N ≥ 1);
- `{"kind": "sim_time", "sim_time": ...}`: the first step whose sim time is at or after it. One
  already in the past when the scenario starts is counted as missed and never fires.

When steps are skipped (real-time overrun), every event in the gap fires, in order, before the
longer step. Events on the same step fire in list order. The player is pure: the engine calls
`due` under its compute lock, so a test-mode run is deterministic.
"""

import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from powerflow.conditions.models import ActiveConditions, ConditionChange, validate_change
from powerflow.errors import PowerflowError
from powerflow.site_config import SiteConfig


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StepTrigger(_Strict):
    kind: Literal["step"] = "step"
    step: int = Field(ge=1, description="Fires before the Nth step after the scenario starts.")


class TimeTrigger(_Strict):
    kind: Literal["sim_time"] = "sim_time"
    sim_time: AwareDatetime = Field(description="Fires before the first step at or after it.")


Trigger = Annotated[StepTrigger | TimeTrigger, Field(discriminator="kind")]


class ScenarioEvent(_Strict):
    at: Trigger
    change: ConditionChange
    label: str | None = Field(default=None, max_length=200)


class EventScenario(_Strict):
    schema_version: Literal[1] = 1
    description: str | None = Field(default=None, max_length=2000)
    events: list[ScenarioEvent] = Field(min_length=1, max_length=1000)


def validate_scenario(scenario: EventScenario, config: SiteConfig) -> list[str]:
    """Every problem with the scenario's changes on this site (empty = valid)."""
    problems: list[str] = []
    for index, event in enumerate(scenario.events, start=1):
        try:
            validate_change(event.change, config)
        except PowerflowError as error:
            problems.append(f"event {index}: {error}")
    return problems


@dataclass(frozen=True)
class ScheduledEvent:
    step: int  # fires before this step is computed
    order: int  # its position in the scenario
    change: ConditionChange


@dataclass(frozen=True)
class ScenarioRun:
    name: str
    started_step: int
    pending: tuple[ScheduledEvent, ...]  # sorted by (step, order)
    total: int
    fired: int = 0
    missed: int = 0


def first_step_at(sim_time: datetime, origin: datetime, step_s: float) -> int:
    """The first step index whose sim time (origin + index·step_s) is ≥ sim_time."""
    return math.ceil((sim_time - origin).total_seconds() / step_s - 1e-9)


def schedule(
    name: str, scenario: EventScenario, started_step: int, origin: datetime, step_s: float
) -> ScenarioRun:
    """Resolve every trigger to a step. started_step is the engine's current step (the next one
    computed is started_step + 1)."""
    events: list[ScheduledEvent] = []
    missed = 0
    for order, event in enumerate(scenario.events):
        match event.at:
            case StepTrigger(step=offset):
                step = started_step + offset
            case TimeTrigger(sim_time=sim_time):
                step = first_step_at(sim_time, origin, step_s)
        if step <= started_step:
            missed += 1
            continue
        events.append(ScheduledEvent(step, order, event.change))
    events.sort(key=lambda item: (item.step, item.order))
    return ScenarioRun(
        name=name,
        started_step=started_step,
        pending=tuple(events),
        total=len(scenario.events),
        missed=missed,
    )


def due(run: ScenarioRun, step_index: int) -> tuple[list[ConditionChange], ScenarioRun]:
    """The changes to apply before computing `step_index`, and the run without them."""
    count = 0
    while count < len(run.pending) and run.pending[count].step <= step_index:
        count += 1
    if count == 0:
        return [], run
    changes = [item.change for item in run.pending[:count]]
    return changes, replace(run, pending=run.pending[count:], fired=run.fired + count)


# -- reporting ---------------------------------------------------------------------------------


class ScenarioStatus(BaseModel):
    name: str
    started_step: int
    total: int = Field(description="Events in the scenario.")
    fired: int
    missed: int = Field(description="sim_time events already in the past at start.")
    next_step: int | None = Field(description="The step the next event fires before.")
    finished: bool


def scenario_status(run: ScenarioRun) -> ScenarioStatus:
    return ScenarioStatus(
        name=run.name,
        started_step=run.started_step,
        total=run.total,
        fired=run.fired,
        missed=run.missed,
        next_step=run.pending[0].step if run.pending else None,
        finished=not run.pending,
    )


class ConditionsReport(ActiveConditions):
    scenario: ScenarioStatus | None = Field(
        description="The event scenario playing (or finished, until stopped or cleared)."
    )


class EventScenarioSummary(BaseModel):
    name: str
    description: str | None
    event_count: int
    valid: bool = Field(description="Whether every event applies to the site as stored now.")
    problems: list[str]
