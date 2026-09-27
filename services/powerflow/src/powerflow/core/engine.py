"""The simulation engine: a real-time asyncio loop around `simulate_step`, plus control.

Real time: tick k is due at anchor + (k − k_anchor)·step_s on the monotonic clock, so sim time
advances 1:1 with wall-clock. When a step overruns and whole ticks are missed, the engine skips
ahead (one longer step, `step_id` jumps), counts the missed ticks in `overrun_count` and logs a
warning. Pausing and resuming re-anchors, so sim time continues from where it paused.

Each step runs in a worker thread (the power flow is CPU-bound) and commits its result under a
lock in that same thread. Stopping waits for an in-flight step, so nothing lands after stop().
"""

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from powerflow.core.runtime import SiteRuntime, load_load_profile, load_pv_profile
from powerflow.core.snapshot import Snapshot
from powerflow.core.state_store import SetpointStore, StateStore
from powerflow.core.step import (
    SimulationState,
    default_setpoints,
    initial_state,
    sim_time_at,
    simulate_step,
)
from powerflow.errors import InvalidStateError, NotInTestModeError
from powerflow.network.solver import SolverFactory
from powerflow.site_config import SiteConfig
from powerflow.storage import ProfileFolder, ProfileStore

logger = logging.getLogger(__name__)

MAX_MANUAL_STEPS = 1_000_000

MonotonicClock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


class RunState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


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


class Engine:
    def __init__(
        self,
        runtime: SiteRuntime,
        solver_factory: SolverFactory,
        profile_store: ProfileStore,
        clock: MonotonicClock = time.monotonic,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self._runtime = runtime
        self._solver_factory = solver_factory
        self._profile_store = profile_store
        self._clock = clock
        self._sleep = sleep
        self._compute_lock = threading.Lock()
        self._control_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._run_state = RunState.STOPPED
        self.store = StateStore(runtime.config.simulation.history_size)
        self.setpoints = SetpointStore(default_setpoints(runtime))
        self._state: SimulationState = initial_state(runtime)
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
            sim_time=sim_time_at(self._runtime, self._state.step_index),
            last_converged=latest.converged if latest is not None else None,
            overrun_count=self._overrun_count,
            nonconverged_count=self._nonconverged_count,
            last_step_duration_ms=duration * 1000 if duration is not None else None,
            history_count=len(self.store),
            history_size=self.store.history_size,
        )

    # -- control ---------------------------------------------------------------------------

    async def start(self) -> None:
        """Start (or resume) the real-time loop. No-op when already running."""
        async with self._control_lock:
            if self._run_state is RunState.RUNNING:
                return
            self._run_state = RunState.RUNNING
            self._task = asyncio.create_task(self._run(), name="powerflow-sim-loop")

    async def pause(self) -> None:
        async with self._control_lock:
            if self._run_state is not RunState.RUNNING:
                raise InvalidStateError(f"can't pause: simulation is {self._run_state}")
            await self._cancel_loop()
            self._run_state = RunState.PAUSED

    async def stop(self) -> None:
        """Stop the loop and keep the state. No-op when already stopped."""
        async with self._control_lock:
            await self._cancel_loop()
            self._run_state = RunState.STOPPED

    async def reset(self) -> None:
        """Stop and return to the initial state: t = start_time, initial SOC, idle setpoints,
        empty history, counters at 0."""
        async with self._control_lock:
            await self._cancel_loop()
            await asyncio.to_thread(self._reset_sync, self._runtime)
            self._run_state = RunState.STOPPED

    async def step(self, count: int) -> Snapshot:
        """Advance `count` steps at once, without real-time pacing (test mode only)."""
        if not self._runtime.config.simulation.test_mode:
            raise NotInTestModeError("manual stepping needs simulation.test_mode: true")
        if not 1 <= count <= MAX_MANUAL_STEPS:
            raise ValueError(f"count must be within 1..{MAX_MANUAL_STEPS}")
        async with self._control_lock:
            if self._run_state is RunState.RUNNING:
                raise InvalidStateError("can't step manually while the simulation is running")
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
            self._run_state = RunState.STOPPED

    # -- internals -------------------------------------------------------------------------

    async def _cancel_loop(self) -> None:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        step_s = self._runtime.config.simulation.step_s
        anchor_wall = self._clock()
        anchor_index = self._state.step_index
        while True:
            next_index = self._state.step_index + 1
            due = anchor_wall + (next_index - anchor_index) * step_s
            delay = due - self._clock()
            if delay > 0:
                await self._sleep(delay)
            missed = int((self._clock() - due) // step_s)
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
                await self._sleep(step_s)

    def _advance_sync(self, step_index: int) -> Snapshot:
        with self._compute_lock:
            started = time.perf_counter()
            outcome = simulate_step(
                self._runtime, self._state, self.setpoints.snapshot(), step_index
            )
            self._state = outcome.state
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
            self._state = initial_state(runtime)
            self.store.clear(runtime.config.simulation.history_size)
            self.setpoints.replace_all(default_setpoints(runtime))
            self._overrun_count = 0
            self._nonconverged_count = 0
            self._last_step_duration_s = None
