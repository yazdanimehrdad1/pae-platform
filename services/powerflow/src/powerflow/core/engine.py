"""The simulation engine: a real-time asyncio loop around `simulate_step`, plus control.

Real time: tick k is due at anchor + (k − k_anchor)·step_s/speed on the monotonic clock, so sim
time advances `speed` × wall-clock (1:1 by default). When a step overruns and whole ticks are
missed, the engine skips ahead (one longer step, `step_id` jumps), counts the missed ticks in
`overrun_count` and logs a warning. Pausing and resuming (and changing the speed) re-anchors, so
sim time continues from where it was.

Clock: the origin (sim time of step 0) is `start_time`, or for "now" the wall clock when a fresh
run starts (or at reset). A run can be scheduled to start at a wall-clock time (SCHEDULED until
then). A fresh run starts at `start_step`.

Each step runs in a worker thread (the power flow is CPU-bound) and commits its result under a
lock in that same thread. Stopping waits for an in-flight step, so nothing lands after stop().
"""

import asyncio
import contextlib
import logging
import threading
import time
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

import numpy as np
from pydantic import BaseModel, Field

from powerflow.conditions import (
    AlarmResetChange,
    ConditionChange,
    FaultCause,
    FaultClock,
    apply_change,
    expire_faults,
    initial_conditions,
    summary,
    validate_change,
)
from powerflow.conditions.scenario import (
    ConditionsReport,
    EventScenario,
    ScenarioRun,
    due_across,
    scenario_status,
    schedule,
    validate_scenario,
)
from powerflow.core.auto_dispatch import (
    AutoDispatchBess,
    AutoDispatchBessSettings,
    AutoDispatchReport,
    AutoDispatchRequest,
    resolve,
)
from powerflow.core.runtime import SiteRuntime, load_load_profile, load_pv_profile
from powerflow.core.snapshot import Snapshot
from powerflow.core.state_store import ConditionStore, SetpointStore, StateStore
from powerflow.core.step import (
    SimulationState,
    default_setpoints,
    initial_state,
    resolve_origin,
    sim_time_at,
    simulate_step,
)
from powerflow.errors import (
    ConditionError,
    InvalidStateError,
    NotFoundError,
    NotInTestModeError,
)
from powerflow.models.auto_dispatch import (
    AutoDispatchBessState,
    AutoDispatchSettings,
    advance,
)
from powerflow.models.auto_dispatch import initial_state as initial_auto_dispatch_state
from powerflow.models.bess import clamp_static
from powerflow.network.solver import SolverFactory
from powerflow.site_config import SiteConfig
from powerflow.storage import ProfileFolder, ProfileStore

logger = logging.getLogger(__name__)

MAX_MANUAL_STEPS = 1_000_000

MonotonicClock = Callable[[], float]
WallClock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    SCHEDULED = "scheduled"  # waiting for its wall-clock start time


class EngineStatus(BaseModel):
    state: RunState
    test_mode: bool
    step_s: float
    step_id: int
    sim_time: datetime
    last_converged: bool | None
    overrun_count: int
    nonconverged_count: int
    last_step_duration_ms: float | None
    history_count: int
    history_size: int
    scenario: str | None = Field(description="The event scenario playing (or finished).")
    speed: float = Field(description="Sim seconds per wall-clock second.")
    start_time: datetime = Field(description='The sim time of step 0 (resolved for "now").')
    start_step: int = Field(description="The step a fresh run or a reset starts from.")
    scheduled_start: datetime | None = Field(description="When a SCHEDULED run starts.")


@dataclass(frozen=True)
class AutoDispatchRun:
    """Auto dispatch while on: the request as sent, and per included BESS its settings and state."""

    request: AutoDispatchRequest
    settings: dict[str, AutoDispatchSettings]
    states: dict[str, AutoDispatchBessState]


class Engine:
    def __init__(
        self,
        runtime: SiteRuntime,
        solver_factory: SolverFactory,
        profile_store: ProfileStore,
        clock: MonotonicClock = time.monotonic,
        sleep: Sleeper = asyncio.sleep,
        wall_clock: WallClock = utc_now,
    ) -> None:
        self._runtime = runtime
        self._solver_factory = solver_factory
        self._profile_store = profile_store
        self._clock = clock
        self._sleep = sleep
        self._wall_clock = wall_clock
        self._compute_lock = threading.Lock()
        self._control_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._run_state = RunState.STOPPED
        self.store = StateStore(runtime.config.simulation.history_size)
        self.setpoints = SetpointStore(default_setpoints(runtime))
        self.conditions = ConditionStore(initial_conditions(runtime.config))
        self._scenarios: list[ScenarioRun] = []  # in start order; they can overlap
        self._auto_dispatch: AutoDispatchRun | None = None  # None = off
        self._state: SimulationState = initial_state(runtime, wall_clock())
        self._speed = runtime.config.simulation.speed
        self._fresh = True  # nothing computed since construction/reset/new config
        self._scheduled_start: datetime | None = None
        self._overrun_count = 0
        self._nonconverged_count = 0
        self._last_step_duration_s: float | None = None

    # -- read side -------------------------------------------------------------------------

    @property
    def runtime(self) -> SiteRuntime:
        return self._runtime

    @property
    def config(self) -> SiteConfig:
        return self._runtime.config

    @property
    def run_state(self) -> RunState:
        return self._run_state

    def status(self) -> EngineStatus:
        latest = self.store.latest
        simulation = self._runtime.config.simulation
        duration = self._last_step_duration_s
        return EngineStatus(
            state=self._run_state,
            test_mode=simulation.test_mode,
            step_s=simulation.step_s,
            step_id=self._state.step_index,
            sim_time=sim_time_at(self._state.origin, simulation.step_s, self._state.step_index),
            last_converged=latest.converged if latest is not None else None,
            overrun_count=self._overrun_count,
            nonconverged_count=self._nonconverged_count,
            last_step_duration_ms=duration * 1000 if duration is not None else None,
            history_count=len(self.store),
            history_size=self.store.history_size,
            scenario=self._scenarios[-1].name if self._scenarios else None,
            speed=self._speed,
            start_time=self._state.origin,
            start_step=simulation.start_step,
            scheduled_start=self._scheduled_start,
        )

    def active_conditions(self) -> ConditionsReport:
        active = summary(self.conditions.snapshot(), self._runtime.config, self._state.origin)
        step_index = self._state.step_index
        statuses = [scenario_status(run, step_index) for run in self._scenarios]
        return ConditionsReport(
            **dict(active),
            scenario=statuses[-1] if statuses else None,
            scenarios=statuses,
        )

    # -- conditions ------------------------------------------------------------------------

    def apply_condition(self, change: ConditionChange) -> ConditionsReport:
        """Apply an injected condition now (any run state); the next step sees it. Raises
        UnknownAssetError / ConditionError when it doesn't fit the active site. A playing event
        scenario keeps playing: the latest change wins."""
        validate_change(change, self._runtime.config)
        step_index, clock = self._state.step_index, self._fault_clock()
        self.conditions.update(lambda current: apply_change(current, change, step_index, clock))
        return self.active_conditions()

    def reset_alarms(self, asset_id: str) -> list[FaultCause]:
        """Alarm reset (AlmRst = 1) on a BESS or PV: drops its latched faults and returns their
        causes. A cause still injected stays, so the asset stays tripped."""
        change = AlarmResetChange(asset_id=asset_id)
        validate_change(change, self._runtime.config)
        before = self.conditions.snapshot().faults.get(asset_id, {})
        latched = [cause for cause, entry in sorted(before.items()) if entry.latched]
        self.apply_condition(change)
        return latched

    def clear_conditions(self) -> ConditionsReport:
        """Stop the event scenario and return to the site config's breakers, nothing injected."""
        with self._compute_lock:
            self._scenarios = []
            self.conditions.replace_all(initial_conditions(self._runtime.config))
        return self.active_conditions()

    async def start_scenario(
        self, name: str, scenario: EventScenario, at_step: int | None = None
    ) -> ConditionsReport:
        """Play an event scenario from the next step, or schedule it so engine step `at_step` is
        its step 1. Other scenarios keep playing (they overlap: the later change wins).
        InvalidStateError (409) while this one is still scheduled or playing; ConditionError if
        an event doesn't fit the active site or `at_step` isn't ahead."""
        problems = validate_scenario(scenario, self._runtime.config)
        if problems:
            raise ConditionError("; ".join(problems))
        await asyncio.to_thread(self._start_scenario_sync, name, scenario, at_step)
        return self.active_conditions()

    async def stop_scenario(self, name: str | None = None) -> ConditionsReport:
        """Stop one run (NotFoundError if it isn't listed), or every run; the conditions they
        set stay."""
        await asyncio.to_thread(self._stop_scenario_sync, name)
        return self.active_conditions()

    # -- auto dispatch ---------------------------------------------------------------------

    @property
    def auto_dispatch_enabled(self) -> bool:
        return self._auto_dispatch is not None

    def auto_dispatch_drives(self, asset_id: str) -> bool:
        """Whether auto dispatch is on and this BESS is included (its setpoints are auto's)."""
        run = self._auto_dispatch
        return run is not None and asset_id in run.settings

    def auto_dispatch_status(self) -> AutoDispatchReport:
        run = self._auto_dispatch
        if run is None:
            return AutoDispatchReport(
                enabled=False,
                power_pct=None,
                defaults=AutoDispatchBessSettings(),
                bess_overrides={},
                bess=[],
            )
        simulation = self._runtime.config.simulation
        now = sim_time_at(self._state.origin, simulation.step_s, self._state.step_index)
        rows: list[AutoDispatchBess] = []
        for asset_id, asset in self._runtime.bess.items():
            settings, state = run.settings.get(asset_id), run.states.get(asset_id)
            resting_until_s = state.resting_until_s if state is not None else None
            rest_remaining_s = (
                max(resting_until_s - now.timestamp(), 0.0) if resting_until_s is not None else None
            )
            rows.append(
                AutoDispatchBess(
                    asset_id=asset_id,
                    included=settings is not None,
                    phase=state.phase if state is not None else None,
                    direction=state.direction if state is not None else None,
                    soc_pct=self._state.bess[asset_id].soc_pct,
                    soc_min_pct=asset.params.soc_min_pct,
                    soc_max_pct=asset.params.soc_max_pct,
                    soc_low_pct=settings.soc_low_pct if settings else None,
                    soc_high_pct=settings.soc_high_pct if settings else None,
                    rest_s=settings.rest_s if settings else None,
                    rest_remaining_s=rest_remaining_s,
                    p_noise_std_pct=settings.p_noise_std_pct if settings else None,
                    ramp_kw_per_s=settings.ramp_kw_per_s if settings else None,
                    q_kvar=settings.q_kvar if settings else None,
                )
            )
        return AutoDispatchReport(
            enabled=True,
            power_pct=run.request.power_pct,
            defaults=run.request.defaults,
            bess_overrides=run.request.bess,
            bess=rows,
        )

    def set_auto_dispatch(self, request: AutoDispatchRequest) -> AutoDispatchReport:
        """Turn auto dispatch on (each included BESS cycles inside its SOC window from the next
        step) or off, or change its settings. Works in any run state. A BESS that stays included
        keeps its direction and rest; one that leaves auto dispatch (excluded, or turned off)
        goes back to idle. UnknownAssetError for an override of no BESS; AutoDispatchError for a
        window that doesn't fit its battery. While a BESS is driven, SetpointService rejects its
        writes."""
        for asset_id in request.bess:
            self._runtime.bess_asset(asset_id)
        settings: dict[str, AutoDispatchSettings] = {}
        if request.enabled:
            for asset_id, asset in self._runtime.bess.items():
                override = request.bess.get(asset_id)
                resolved = resolve(asset_id, asset.params, request.defaults, override)
                if resolved is not None:
                    settings[asset_id] = resolved
        with self._compute_lock:
            current = self._auto_dispatch
            previous_states = current.states if current is not None else {}
            idle = default_setpoints(self._runtime).bess
            for asset_id in previous_states:
                if asset_id not in settings:
                    self.setpoints.set_bess(asset_id, idle[asset_id])
            if not request.enabled:
                self._auto_dispatch = None
                return self.auto_dispatch_status()
            states = {
                asset_id: previous_states.get(asset_id)
                or initial_auto_dispatch_state(resolved, self._state.bess[asset_id].soc_pct)
                for asset_id, resolved in settings.items()
            }
            self._auto_dispatch = AutoDispatchRun(request, settings, states)
            return self.auto_dispatch_status()

    # -- control ---------------------------------------------------------------------------

    async def start(self, at: datetime | None = None) -> None:
        """Start (or resume) the real-time loop: now, or at the wall-clock time `at` (SCHEDULED
        until then; a time already past starts now). No-op when already running; a new start
        replaces a schedule."""
        async with self._control_lock:
            if self._run_state is RunState.RUNNING:
                return
            await self._cancel_loop()  # a pending schedule
            self._scheduled_start = None
            if at is not None and at > self._wall_clock():
                self._scheduled_start = at
                self._run_state = RunState.SCHEDULED
                self._task = asyncio.create_task(self._run_at(at), name="powerflow-sim-schedule")
                return
            self._begin_run()
            self._task = asyncio.create_task(self._run(), name="powerflow-sim-loop")

    async def set_speed(self, speed: float) -> None:
        """Change the speed factor (0 < speed ≤ 100), in any state; a running loop re-anchors."""
        if not 0 < speed <= 100:
            raise ValueError("speed must be within (0, 100]")
        async with self._control_lock:
            self._speed = speed
            if self._run_state is RunState.RUNNING:
                await self._cancel_loop()
                self._task = asyncio.create_task(self._run(), name="powerflow-sim-loop")

    async def pause(self) -> None:
        async with self._control_lock:
            if self._run_state is not RunState.RUNNING:
                raise InvalidStateError(f"can't pause: simulation is {self._run_state}")
            await self._cancel_loop()
            self._run_state = RunState.PAUSED

    async def stop(self) -> None:
        """Stop the loop (or cancel a scheduled start) and keep the state."""
        async with self._control_lock:
            await self._cancel_loop()
            self._scheduled_start = None
            self._run_state = RunState.STOPPED

    async def reset(self) -> None:
        """Stop and return to the initial state: step start_step at the origin ("now" is read
        again), initial SOC, idle setpoints, the config's breakers with nothing injected, the
        config's speed, empty history, counters at 0."""
        async with self._control_lock:
            await self._cancel_loop()
            await asyncio.to_thread(self._reset_sync, self._runtime)
            self._scheduled_start = None
            self._run_state = RunState.STOPPED

    async def step(self, count: int) -> Snapshot:
        """Advance `count` steps at once, without real-time pacing (test mode only)."""
        if not self._runtime.config.simulation.test_mode:
            raise NotInTestModeError("manual stepping needs simulation.test_mode: true")
        if not 1 <= count <= MAX_MANUAL_STEPS:
            raise ValueError(f"count must be within 1..{MAX_MANUAL_STEPS}")
        async with self._control_lock:
            if self._run_state in (RunState.RUNNING, RunState.SCHEDULED):
                raise InvalidStateError(
                    f"can't step manually while the simulation is {self._run_state}"
                )
            return await asyncio.to_thread(self._step_many_sync, count)

    async def replace_config(self, config: SiteConfig) -> None:
        """Rebuild everything from a new config and reset. Only while stopped. Raises
        ProfileError (and leaves the current config in place) if a profile can't be loaded."""
        async with self._control_lock:
            if self._run_state is not RunState.STOPPED:
                raise InvalidStateError("stop the simulation before replacing the config")
            runtime = await asyncio.to_thread(
                SiteRuntime.build, config, self._profile_store, self._solver_factory
            )
            await asyncio.to_thread(self._reset_sync, runtime)

    async def reload_scenario(self, folder: ProfileFolder, scenario: str) -> list[str]:
        """Re-read a profile scenario from disk into every asset that uses it (works while
        running; the next step sees it). Returns the ids of the assets reloaded."""
        runtime = self._runtime
        reloaded: list[str] = []
        if folder is ProfileFolder.LOAD:
            for asset_id, load in runtime.loads.items():
                if load.config.profile.scenario == scenario:
                    profile = await asyncio.to_thread(
                        load_load_profile, self._profile_store, load.config
                    )
                    with self._compute_lock:
                        load.profile = profile
                    reloaded.append(asset_id)
        else:
            for asset_id, pv in runtime.pv.items():
                if pv.config.availability.scenario == scenario:
                    profile = await asyncio.to_thread(
                        load_pv_profile, self._profile_store, pv.config
                    )
                    with self._compute_lock:
                        pv.profile = profile
                    reloaded.append(asset_id)
        return reloaded

    async def shutdown(self) -> None:
        async with self._control_lock:
            await self._cancel_loop()
            self._scheduled_start = None
            self._run_state = RunState.STOPPED

    # -- internals -------------------------------------------------------------------------

    async def _cancel_loop(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def _begin_run(self) -> None:
        """Enter RUNNING; a fresh run with start_time "now" takes its origin from the wall
        clock now."""
        simulation = self._runtime.config.simulation
        if self._fresh and simulation.start_time == "now":
            origin = resolve_origin(simulation, self._wall_clock())
            self._state = replace(self._state, origin=origin)
        self._run_state = RunState.RUNNING

    async def _run_at(self, at: datetime) -> None:
        delay = (at - self._wall_clock()).total_seconds()
        if delay > 0:
            await self._sleep(delay)
        self._scheduled_start = None
        self._begin_run()
        await self._run()

    async def _run(self) -> None:
        step_s = self._runtime.config.simulation.step_s
        period_s = step_s / self._speed  # wall-clock seconds per step
        anchor_wall = self._clock()
        anchor_index = self._state.step_index
        while True:
            next_index = self._state.step_index + 1
            due = anchor_wall + (next_index - anchor_index) * period_s
            delay = due - self._clock()
            if delay > 0:
                await self._sleep(delay)
            missed = int((self._clock() - due) // period_s)
            if missed >= 1:
                self._overrun_count += missed
                logger.warning(
                    "step %d overran by %d tick(s); skipping ahead to stay on wall-clock",
                    next_index,
                    missed,
                )
            step = asyncio.ensure_future(
                asyncio.to_thread(self._advance_sync, next_index + max(missed, 0))
            )
            try:
                await asyncio.shield(step)
            except asyncio.CancelledError:
                # Let an in-flight step finish, so stop/pause return with a settled state.
                await step
                raise
            except Exception:
                # Never let one bad step kill the loop; the step itself logs non-convergence.
                logger.exception("step %d failed", next_index)
                await self._sleep(period_s)

    def _start_scenario_sync(self, name: str, scenario: EventScenario, at_step: int | None) -> None:
        with self._compute_lock:
            current = self._state.step_index
            if any(run.name == name and run.pending for run in self._scenarios):
                raise InvalidStateError(
                    f"event scenario {name!r} is already scheduled or playing; stop it first"
                )
            if at_step is not None and at_step <= current:
                raise ConditionError(f"at_step must be after the current step {current}")
            started_step = current if at_step is None else at_step - 1
            step_s = self._runtime.config.simulation.step_s
            run = schedule(name, scenario, started_step, self._state.origin, step_s)
            # A finished run of the same scenario gives way to the new one.
            self._scenarios = [item for item in self._scenarios if item.name != name] + [run]

    def _stop_scenario_sync(self, name: str | None) -> None:
        with self._compute_lock:
            if name is None:
                self._scenarios = []
                return
            if not any(run.name == name for run in self._scenarios):
                raise NotFoundError(f"event scenario {name!r} isn't scheduled or playing")
            self._scenarios = [run for run in self._scenarios if run.name != name]

    def _play_scenario(self, step_index: int) -> None:
        """Apply every run's changes due before `step_index` (under the compute lock)."""
        if not self._scenarios:
            return
        changes, self._scenarios = due_across(self._scenarios, step_index)
        published_step, clock = self._state.step_index, self._fault_clock()
        for change in changes:
            self.conditions.update(
                lambda current, change=change: apply_change(current, change, published_step, clock)
            )

    def _apply_auto_dispatch(self, step_index: int) -> None:
        """Advance each driven BESS to `step_index` and write its setpoint (under the compute
        lock). Noise draws are keyed on (seed, step, BESS), so a run is reproducible."""
        run = self._auto_dispatch
        if run is None:
            return
        simulation = self._runtime.config.simulation
        dt_s = (step_index - self._state.step_index) * simulation.step_s
        t_s = sim_time_at(self._state.origin, simulation.step_s, step_index).timestamp()
        states: dict[str, AutoDispatchBessState] = {}
        for asset_id, settings in run.settings.items():
            params = self._runtime.bess[asset_id].params
            stream = zlib.crc32(asset_id.encode())
            rng = np.random.default_rng((simulation.seed, step_index, stream))
            state, setpoint = advance(
                params,
                settings,
                run.states[asset_id],
                self._state.bess[asset_id].soc_pct,
                t_s,
                dt_s,
                run.request.power_pct,
                float(rng.standard_normal()),
            )
            p_kw, q_kvar, _ = clamp_static(params, setpoint.p_kw, setpoint.q_kvar)
            states[asset_id] = replace(state, p_cmd_kw=p_kw)
            self.setpoints.set_bess(asset_id, replace(setpoint, p_kw=p_kw, q_kvar=q_kvar))
        self._auto_dispatch = replace(run, states=states)

    def _fault_clock(self) -> FaultClock:
        simulation = self._runtime.config.simulation
        return FaultClock(seed=simulation.seed, step_s=simulation.step_s)

    def _advance_sync(self, step_index: int) -> Snapshot:
        with self._compute_lock:
            started = time.perf_counter()
            self._play_scenario(step_index)
            # Auto-restore faults due by this step go (so the report shows them gone too).
            self.conditions.update(lambda current: expire_faults(current, step_index))
            self._apply_auto_dispatch(step_index)
            outcome = simulate_step(
                self._runtime,
                self._state,
                self.setpoints.snapshot(),
                step_index,
                self.conditions.snapshot(),
            )
            self._state = outcome.state
            self._fresh = False
            if outcome.error is not None:
                self._nonconverged_count += 1
            self.store.publish(outcome.snapshot)
            self._last_step_duration_s = time.perf_counter() - started
            return outcome.snapshot

    def _step_many_sync(self, count: int) -> Snapshot:
        snapshot: Snapshot | None = None
        for _ in range(count):
            snapshot = self._advance_sync(self._state.step_index + 1)
        assert snapshot is not None
        return snapshot

    def _reset_sync(self, runtime: SiteRuntime) -> None:
        with self._compute_lock:
            self._runtime = runtime
            self._state = initial_state(runtime, self._wall_clock())
            self._speed = runtime.config.simulation.speed
            self._fresh = True
            self.store.clear(runtime.config.simulation.history_size)
            self.setpoints.replace_all(default_setpoints(runtime))
            self.conditions.replace_all(initial_conditions(runtime.config))
            self._scenarios = []
            self._auto_dispatch = None
            self._overrun_count = 0
            self._nonconverged_count = 0
            self._last_step_duration_s = None
