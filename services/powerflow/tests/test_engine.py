"""Step pipeline and engine: determinism, 24 h SOC, power balance, non-convergence, real-time
pacing and overruns (with an injected clock, so no test waits on wall time)."""

import asyncio
import math
from collections.abc import Callable
from typing import Any

import pytest
from conftest import PROFILES, site_config_dict

from powerflow.core.engine import Engine, RunState
from powerflow.core.runtime import SiteRuntime
from powerflow.core.snapshot import Snapshot
from powerflow.errors import InvalidStateError, NonConvergenceError, NotInTestModeError
from powerflow.models.bess import BessMode, BessSetpoint
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.network.solver import Injection, NetworkResult, PowerFlowSolver
from powerflow.network.topology import Topology
from powerflow.site_config import SiteConfig


def make_engine(
    raw: dict[str, Any] | None = None,
    solver_factory: Callable[[Topology], PowerFlowSolver] = PandapowerSolver,
    **engine_kwargs: Any,
) -> Engine:
    config = SiteConfig.model_validate(raw or site_config_dict())
    runtime = SiteRuntime.build(config, PROFILES, solver_factory)
    return Engine(runtime, solver_factory, PROFILES, **engine_kwargs)


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def discharge(engine: Engine, p_kw: float, q_kvar: float = 0.0) -> None:
    for asset_id in engine.runtime.bess:
        engine.setpoints.set_bess(asset_id, BessSetpoint(p_kw, q_kvar, BessMode.PQ))


class TestManualStepping:
    def test_steps_advance_sim_time_and_step_id(self) -> None:
        engine = make_engine()
        snapshot = run(engine.step(3))
        assert snapshot.step_id == 3 and snapshot.converged
        assert snapshot.sim_time.isoformat() == "2026-06-21T12:00:03+00:00"
        assert [item.step_id for item in engine.store.history()] == [1, 2, 3]

    def test_step_requires_test_mode(self) -> None:
        raw = site_config_dict()
        raw["simulation"]["test_mode"] = False
        with pytest.raises(NotInTestModeError):
            run(make_engine(raw).step(1))

    def test_deterministic_for_same_inputs(self) -> None:
        raw = site_config_dict(n_bess=2, n_pv=1)
        raw["loads"][0]["noise"] = {"p_std_pct": 2, "q_std_pct": 2}

        def scenario() -> list[Snapshot]:
            engine = make_engine(raw)
            run(engine.step(5))
            discharge(engine, 1200, -100)
            run(engine.step(5))
            return engine.store.history()

        assert scenario() == scenario()

    def test_power_balance_through_the_pipeline(self) -> None:
        engine = make_engine(site_config_dict(n_bess=2, n_pv=2))
        discharge(engine, 800)
        snapshot = run(engine.step(2))
        generation = sum(item.p_kw for item in snapshot.bess) + sum(
            item.p_kw for item in snapshot.pv
        )
        consumption = sum(item.p_kw for item in snapshot.loads) + sum(
            item.aux_p_kw for item in snapshot.bess
        )
        expected = generation - consumption - snapshot.poi.p_loss_total_kw
        assert snapshot.poi.p_kw == pytest.approx(expected, abs=0.05)

    def test_24h_soc_behaviour(self) -> None:
        """A 24 h day at 60 s steps: discharge until SOC min, charge until SOC max. The SOC
        must stop exactly at each limit and the energy must match the efficiencies."""
        raw = site_config_dict(n_bess=1, n_pv=0)
        raw["simulation"]["step_s"] = 60
        raw["bess"][0]["battery"].update(
            {"efficiency": {"charge": 0.95, "discharge": 0.95}, "soc_initial_pct": 50}
        )
        engine = make_engine(raw)
        soc: list[float] = []
        discharge(engine, 2000)
        for _ in range(12 * 60):  # 12 h discharging at 2 MW: empties after ~2.2 h
            soc.append(run(engine.step(1)).bess[0].soc_pct)
        discharge(engine, -2000)
        for _ in range(12 * 60):  # 12 h charging: full after ~4.7 h
            soc.append(run(engine.step(1)).bess[0].soc_pct)

        assert min(soc) == pytest.approx(5) and max(soc) == pytest.approx(95)
        assert all(5 - 1e-9 <= value <= 95 + 1e-9 for value in soc)
        # 45 % of 10 MWh = 4500 kWh in the cells; delivered 4275 kWh at 2 MW = 128.25 min.
        minutes_to_empty = next(index for index, value in enumerate(soc) if value <= 5 + 1e-9) + 1
        assert minutes_to_empty == 129
        # 90 % = 9000 kWh stored at 1900 kW into the cells = 284.2 min.
        minutes_to_full = (
            next(index for index, value in enumerate(soc[720:]) if value >= 95 - 1e-9) + 1
        )
        assert minutes_to_full == 285
        last = engine.store.latest
        assert last is not None and last.bess[0].limit_flag_names == ["SOC_LIMIT"]


class FlakySolver(PowerFlowSolver):
    """Delegates to pandapower but fails on chosen solve calls."""

    def __init__(self, topology: Topology, fail_on: set[int]) -> None:
        self._inner = PandapowerSolver(topology)
        self._fail_on = fail_on
        self.calls = 0

    def solve(self, injections: dict[str, Injection]) -> NetworkResult:
        self.calls += 1
        if self.calls in self._fail_on:
            raise NonConvergenceError("forced")
        return self._inner.solve(injections)


class TestNonConvergence:
    def test_failed_step_keeps_last_good_state(self) -> None:
        engine = make_engine(solver_factory=lambda topology: FlakySolver(topology, {3}))
        discharge(engine, 1000)
        run(engine.step(2))
        good = engine.store.latest
        assert good is not None and good.converged

        failed = run(engine.step(1))
        assert failed.step_id == 3 and not failed.converged
        assert failed.bess == good.bess  # last good values
        stale_fields = {"meter_state", "meter_state_name"}
        assert failed.poi.model_dump(exclude=stale_fields) == good.poi.model_dump(
            exclude=stale_fields
        )
        assert failed.poi.meter_state_name == "STALE"
        assert engine.status().nonconverged_count == 1
        assert engine.status().last_converged is False

        recovered = run(engine.step(1))
        assert recovered.converged and recovered.step_id == 4
        # SOC did not advance during the failed step: 3 steps of discharge, not 4.
        assert recovered.bess[0].soc_pct == pytest.approx(50 - 3 * 1000 / 0.95 / 3600 / 10000 * 100)

    def test_failure_before_any_good_step(self) -> None:
        engine = make_engine(solver_factory=lambda topology: FlakySolver(topology, {1}))
        snapshot = run(engine.step(1))
        assert not snapshot.converged and snapshot.poi.v_pu == 0


def metered_site() -> dict[str, Any]:
    raw = site_config_dict(n_bess=1, n_pv=1)
    raw["meters"] = [
        {"id": "m_bess1", "transformer": "bess1"},
        {"id": "m_pv1", "transformer": "pv1"},
    ]
    return raw


class TestFeederMeters:
    def test_meter_reads_the_transformer_hv_side(self) -> None:
        engine = make_engine(metered_site())
        discharge(engine, 1000, 200)
        snapshot = run(engine.step(1))
        meters = {meter.id: meter for meter in snapshot.meters}
        transformers = {item.name: item for item in snapshot.transformers}
        bess = snapshot.bess[0]

        # + toward the MV bus, after the transformer losses (and the aux load on the LV bus).
        tx = transformers["tx:bess1"]
        assert meters["m_bess1"].p_kw == pytest.approx(bess.p_kw - bess.aux_p_kw - tx.p_loss_kw)
        assert meters["m_bess1"].q_kvar == pytest.approx(tx.q_hv_kvar)
        assert meters["m_pv1"].p_kw == pytest.approx(
            snapshot.pv[0].p_kw - transformers["tx:pv1"].p_loss_kw
        )
        collector = next(bus for bus in snapshot.buses if bus.name == "col:mv1")
        assert meters["m_bess1"].v_kv == pytest.approx(collector.v_kv)
        # I = S / (√3·V) on the HV side.
        assert meters["m_bess1"].i_a == pytest.approx(
            meters["m_bess1"].s_kva / (math.sqrt(3) * collector.v_kv), rel=1e-3
        )
        assert meters["m_bess1"].meter_state_name == "OK"

    def test_feeder_meters_add_up_to_the_poi(self) -> None:
        """With every generator metered and the load on the POI bus: POI = Σ meters − load."""
        engine = make_engine(metered_site())
        discharge(engine, -800)
        snapshot = run(engine.step(1))
        metered = sum(meter.p_kw for meter in snapshot.meters)
        assert snapshot.poi.p_kw == pytest.approx(metered - snapshot.loads[0].p_kw, abs=0.01)

    def test_feeder_meters_go_stale_on_non_convergence(self) -> None:
        engine = make_engine(
            metered_site(), solver_factory=lambda topology: FlakySolver(topology, {2})
        )
        good = run(engine.step(1))
        failed = run(engine.step(1))
        assert [meter.meter_state_name for meter in failed.meters] == ["STALE", "STALE"]
        assert [meter.p_kw for meter in failed.meters] == [meter.p_kw for meter in good.meters]


class FakeClock:
    """Monotonic time that only moves when the engine sleeps (or a solver 'computes')."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


class SlowSolver(PowerFlowSolver):
    """Advances the fake clock during chosen solves, simulating an overrun."""

    def __init__(self, topology: Topology, clock: FakeClock, slow_calls: dict[int, float]) -> None:
        self._inner = PandapowerSolver(topology)
        self._clock = clock
        self._slow_calls = slow_calls
        self.calls = 0

    def solve(self, injections: dict[str, Injection]) -> NetworkResult:
        self.calls += 1
        self._clock.now += self._slow_calls.get(self.calls, 0.0)
        return self._inner.solve(injections)


async def run_until(engine: Engine, step_id: int) -> None:
    await engine.start()
    for _ in range(10_000):
        latest = engine.store.latest
        if latest is not None and latest.step_id >= step_id:
            break
        await asyncio.sleep(0.001)
    await engine.stop()


class TestRealTimeLoop:
    def test_one_step_per_period(self) -> None:
        clock = FakeClock()
        engine = make_engine(clock=clock, sleep=clock.sleep)
        start = clock.now
        run(run_until(engine, 5))
        history = [snapshot.step_id for snapshot in engine.store.history()]
        assert history[:5] == [1, 2, 3, 4, 5]
        # One period per step (the loop may already be sleeping toward the next tick at stop).
        assert len(history) <= clock.now - start <= len(history) + 1
        assert engine.status().overrun_count == 0

    def test_overrun_skips_ahead_and_counts(self) -> None:
        clock = FakeClock()
        solvers: list[SlowSolver] = []

        def factory(topology: Topology) -> PowerFlowSolver:
            solvers.append(SlowSolver(topology, clock, {2: 2.5}))  # step 2 takes 2.5 periods
            return solvers[-1]

        engine = make_engine(solver_factory=factory, clock=clock, sleep=clock.sleep)
        run(run_until(engine, 6))
        step_ids = [snapshot.step_id for snapshot in engine.store.history()]
        # Step 2 started at t = 2 and finished at t = 4.5: tick 3 was missed, tick 4 runs
        # (0.5 s late).
        assert step_ids[:4] == [1, 2, 4, 5]
        assert engine.status().overrun_count == 1
        # The skipped tick is integrated as one longer step; sim time stays on the grid.
        assert engine.store.history()[2].sim_time.isoformat() == "2026-06-21T12:00:04+00:00"

    def test_nothing_lands_after_stop(self) -> None:
        clock = FakeClock()
        engine = make_engine(clock=clock, sleep=clock.sleep)

        async def scenario() -> None:
            await run_until(engine, 3)
            count = len(engine.store)
            await asyncio.sleep(0.1)  # longer than a step takes
            assert len(engine.store) == count

        run(scenario())

    def test_pause_resume_and_state_rules(self) -> None:
        clock = FakeClock()
        engine = make_engine(clock=clock, sleep=clock.sleep)

        async def scenario() -> None:
            with pytest.raises(InvalidStateError):
                await engine.pause()  # not running
            await run_until(engine, 2)
            await engine.start()
            await asyncio.sleep(0.01)
            with pytest.raises(InvalidStateError):
                await engine.step(1)  # running
            await engine.pause()
            assert engine.run_state is RunState.PAUSED
            paused_at = engine.status().step_id
            clock.now += 100  # wall time passes while paused
            await run_until(engine, paused_at + 2)
            history = [snapshot.step_id for snapshot in engine.store.history()]
            # Resuming re-anchors: no jump for the 100 s spent paused.
            assert history[history.index(paused_at) + 1] == paused_at + 1
            await engine.reset()
            assert engine.status().step_id == 0 and engine.store.latest is None

        run(scenario())
