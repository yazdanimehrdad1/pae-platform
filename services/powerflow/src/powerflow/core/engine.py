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
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from powerflow.conditions import (
    ConditionChange,
    apply_change,
    initial_conditions,
    summary,
    validate_change,
)
from powerflow.conditions.scenario import (
    ConditionsReport,
    EventScenario,
    ScenarioRun,
    due,
    scenario_status,
    schedule,
    validate_scenario,
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
from powerflow.errors import ConditionError, InvalidStateError, NotInTestModeError
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
        self._scenario: ScenarioRun | None = None
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
            scenario=self._scenario.name if self._scenario is not None else None,
            speed=self._speed,
            start_time=self._state.origin,
            start_step=simulation.start_step,
            scheduled_start=self._scheduled_start,
        )

    def active_conditions(self) -> ConditionsReport:
        active = summary(self.conditions.snapshot(), self._runtime.config)
        run = self._scenario
        return ConditionsReport(
            **dict(active),
            scenario=scenario_status(run) if run is not None else None,
        )

    # -- conditions ------------------------------------------------------------------------

    def apply_condition(self, change: ConditionChange) -> ConditionsReport:
        """Apply an injected condition now (any run state); the next step sees it. Raises
        UnknownAssetError / ConditionError when it doesn't fit the active site. A playing event
        scenario keeps playing: the latest change wins."""
        validate_change(change, self._runtime.config)
        step_index = self._state.step_index
        self.conditions.update(lambda current: apply_change(current, change, step_index))
        return self.active_conditions()

    def clear_conditions(self) -> ConditionsReport:
        """Stop the event scenario and return to the site config's breakers, nothing injected."""
        with self._compute_lock:
            self._scenario = None
            self.conditions.replace_all(initial_conditions(self._runtime.config))
        return self.active_conditions()

    async def start_scenario(self, name: str, scenario: EventScenario) -> ConditionsReport:
        """Play an event scenario from the current step. 409 while another one is still
        playing; ConditionError if an event doesn't fit the active site."""
        problems = validate_scenario(scenario, self._runtime.config)
        if problems:
            raise ConditionError("; ".join(problems))
        await asyncio.to_thread(self._start_scenario_sync, name, scenario)
        return self.active_conditions()

    async def stop_scenario(self) -> ConditionsReport:
        """Stop the event scenario; the conditions it set stay."""
        await asyncio.to_thread(self._stop_scenario_sync)
        return self.active_conditions()

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

    def _start_scenario_sync(self, name: str, scenario: EventScenario) -> None:
        with self._compute_lock:
            if self._scenario is not None and self._scenario.pending:
                raise InvalidStateError(
                    f"event scenario {self._scenario.name!r} is playing; stop it first"
                )
            step_s = self._runtime.config.simulation.step_s
            self._scenario = schedule(
                name, scenario, self._state.step_index, self._state.origin, step_s
            )

    def _stop_scenario_sync(self) -> None:
        with self._compute_lock:
            self._scenario = None

    def _play_scenario(self, step_index: int) -> None:
        """Apply the event scenario's changes due before `step_index` (under the compute lock)."""
        if self._scenario is None:
            return
        changes, self._scenario = due(self._scenario, step_index)
        published_step = self._state.step_index
        for change in changes:
            self.conditions.update(
                lambda current, change=change: apply_change(current, change, published_step)
            )

    def _advance_sync(self, step_index: int) -> Snapshot:
        with self._compute_lock:
            started = time.perf_counter()
            self._play_scenario(step_index)
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
            self._scenario = None
            self._overrun_count = 0
            self._nonconverged_count = 0
            self._last_step_duration_s = None
