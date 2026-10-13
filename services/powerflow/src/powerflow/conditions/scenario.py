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
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

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


class ExpectedPoint(_Strict):
    """What one point-standard point (a Modbus register) should read while the scenario plays:
    `equals` (a number, or for an enum point its symbol, e.g. "FAULT") and/or bits of a bitfield
    point that must be set or clear, on every step from `from_step` to `to_step`."""

    device: str = Field(
        description='Device label: "<kind>.<id>", e.g. "bess.bess1", "pv.pv1", "load.load1", '
        '"feeder_meter.m_bess1", "poi_meter.meter", "site.site".'
    )
    point: str = Field(description='Standard point name, e.g. "InvSt", "Alrm", "W".')
    equals: float | str | None = Field(
        default=None, description="A number (SI units), or an enum symbol of the point."
    )
    tolerance: float = Field(default=0.0, ge=0, description="For a numeric `equals`.")
    bits_set: list[str] = Field(default_factory=list, description="Bit labels that must be set.")
    bits_clear: list[str] = Field(
        default_factory=list, description="Bit labels that must be clear."
    )
    from_step: int = Field(ge=1, description="Steps after the start, counted like StepTrigger.")
    to_step: int | None = Field(default=None, description="Inclusive; null = only from_step.")
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _something_to_check(self) -> Self:
        if self.equals is None and not self.bits_set and not self.bits_clear:
            raise ValueError("give equals, bits_set or bits_clear")
        if self.to_step is not None and self.to_step < self.from_step:
            raise ValueError("to_step must be ≥ from_step")
        return self

    @property
    def last_step(self) -> int:
        return self.to_step if self.to_step is not None else self.from_step


class EventScenario(_Strict):
    schema_version: Literal[1] = 1
    description: str | None = Field(
        default=None, max_length=2000, description="What the scenario does."
    )
    events: list[ScenarioEvent] = Field(min_length=1, max_length=1000)
    expected_points: list[ExpectedPoint] = Field(
        default_factory=list,
        max_length=200,
        description="The impacted points and the values they should read, checked by step.",
    )


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
    started_step: int  # its step N fires before engine step started_step + N
    pending: tuple[ScheduledEvent, ...]  # sorted by (step, order)
    total: int
    last_step: int  # the engine step its last event fires before (started_step if none)
    fired: int = 0
    missed: int = 0


def first_step_at(sim_time: datetime, origin: datetime, step_s: float) -> int:
    """The first step index whose sim time (origin + index·step_s) is ≥ sim_time."""
    return math.ceil((sim_time - origin).total_seconds() / step_s - 1e-9)


def schedule(
    name: str, scenario: EventScenario, started_step: int, origin: datetime, step_s: float
) -> ScenarioRun:
    """Resolve every trigger to a step. started_step is the engine step just before the
    scenario's step 1: the current step to start now, or S - 1 to start at step S."""
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
        last_step=max((event.step for event in events), default=started_step),
        missed=missed,
    )


def due_events(run: ScenarioRun, step_index: int) -> tuple[list[ScheduledEvent], ScenarioRun]:
    """The events to apply before computing `step_index`, and the run without them."""
    count = 0
    while count < len(run.pending) and run.pending[count].step <= step_index:
        count += 1
    if count == 0:
        return [], run
    events = list(run.pending[:count])
    return events, replace(run, pending=run.pending[count:], fired=run.fired + count)


def due(run: ScenarioRun, step_index: int) -> tuple[list[ConditionChange], ScenarioRun]:
    """The changes to apply before computing `step_index`, and the run without them."""
    events, run = due_events(run, step_index)
    return [event.change for event in events], run


def due_across(
    runs: list[ScenarioRun], step_index: int
) -> tuple[list[ConditionChange], list[ScenarioRun]]:
    """Several runs at once: every change due before `step_index`, in (step, run start order,
    event order), so overlapping scenarios interleave like one timeline; later changes win."""
    collected: list[tuple[int, int, int, ConditionChange]] = []
    remaining: list[ScenarioRun] = []
    for position, run in enumerate(runs):
        events, run = due_events(run, step_index)
        collected += [(event.step, position, event.order, event.change) for event in events]
        remaining.append(run)
    collected.sort(key=lambda item: item[:3])
    return [item[3] for item in collected], remaining


# -- reporting ---------------------------------------------------------------------------------


RunState = Literal["scheduled", "playing", "finished"]


class ScenarioStatus(BaseModel):
    name: str
    started_step: int = Field(description="The engine step just before the scenario's step 1.")
    start_step: int = Field(description="The engine step that is the scenario's step 1.")
    state: RunState = Field(
        description="scheduled: its step 1 is still ahead; playing: events pending; finished."
    )
    current_step: int | None = Field(
        description="The scenario's own step now (counted like its triggers and expected "
        "points); null while scheduled."
    )
    length: int = Field(description="The scenario step of its last event.")
    total: int = Field(description="Events in the scenario.")
    fired: int
    missed: int = Field(description="sim_time events already in the past at start.")
    next_step: int | None = Field(description="The engine step the next event fires before.")
    finished: bool


def scenario_status(run: ScenarioRun, step_index: int) -> ScenarioStatus:
    """`step_index` is the engine's current (last computed) step."""
    current = step_index - run.started_step
    if not run.pending:
        state: RunState = "finished"
    elif current < 1:
        state = "scheduled"
    else:
        state = "playing"
    return ScenarioStatus(
        name=run.name,
        started_step=run.started_step,
        start_step=run.started_step + 1,
        state=state,
        current_step=current if current >= 1 else None,
        length=run.last_step - run.started_step,
        total=run.total,
        fired=run.fired,
        missed=run.missed,
        next_step=run.pending[0].step if run.pending else None,
        finished=not run.pending,
    )


class ConditionsReport(ActiveConditions):
    scenario: ScenarioStatus | None = Field(
        description="The most recently started or scheduled run (see `scenarios` for all)."
    )
    scenarios: list[ScenarioStatus] = Field(
        description="Every scheduled, playing or finished run, in start order (they can "
        "overlap), until stopped or cleared."
    )


class EventScenarioCategory(StrEnum):
    DEFAULT = "default"  # the built-in library, synced to the default sites; read-only
    CUSTOM = "custom"  # saved through the API


class EventScenarioSummary(BaseModel):
    name: str
    category: EventScenarioCategory = Field(
        description="`default`: a built-in scenario (read-only, synced from powerflow at start); "
        "`custom`: saved "
        "through the API."
    )
    description: str | None = Field(description="What the scenario does.")
    event_count: int
    expected_points: list[ExpectedPoint]
    valid: bool = Field(
        description="Whether every event and expected point applies to the site as stored now."
    )
    problems: list[str]
