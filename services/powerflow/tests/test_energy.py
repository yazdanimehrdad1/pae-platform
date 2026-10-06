"""Energy counters: integrated in the simulation step, exact for batched steps, held while the
power flow fails, published on the snapshot and as measurement points."""

import asyncio
from datetime import date

import pytest
from conftest import PROFILES, site_config_dict
from test_engine import FlakySolver

from powerflow.core.energy import accumulate, integrate
from powerflow.core.engine import Engine
from powerflow.core.runtime import SiteRuntime
from powerflow.core.snapshot import EnergyTotals
from powerflow.models.bess import BessMode, BessSetpoint
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.network.solver import SolverFactory
from powerflow.site_config import SiteConfig

DAY = date(2026, 6, 21)


def make_engine(solver_factory: SolverFactory = PandapowerSolver) -> Engine:
    config = SiteConfig.model_validate(site_config_dict())
    runtime = SiteRuntime.build(config, PROFILES, solver_factory)
    return Engine(runtime, solver_factory, PROFILES)


class TestAccumulate:
    def test_splits_by_direction_and_quadrant(self) -> None:
        totals = accumulate(EnergyTotals(), p_kw=1000, q_kvar=-500, hours=0.5, day=DAY)
        assert totals.wh_positive == 500_000 and totals.wh_negative == 0
        assert totals.varh_negative == 250_000 and totals.varh_q4 == 250_000
        assert totals.vah_positive == pytest.approx((1000**2 + 500**2) ** 0.5 * 500)
        charging = accumulate(totals, p_kw=-200, q_kvar=100, hours=1, day=DAY)
        assert charging.wh_negative == 200_000 and charging.varh_q2 == 100_000
        assert charging.wh_positive == 500_000  # unchanged

    def test_daily_counter_restarts_on_a_new_day(self) -> None:
        today = accumulate(EnergyTotals(), 1000, 0, 1, DAY)
        tomorrow = accumulate(today, 1000, 0, 1, date(2026, 6, 22))
        assert tomorrow.wh_positive_today == 1_000_000
        assert tomorrow.wh_positive == 2_000_000


class TestInSimulation:
    def test_batched_steps_integrate_every_step(self) -> None:
        """Stepping 30 at once counts exactly what 30 single steps count (P·dt per step)."""
        engine = make_engine()
        engine.setpoints.set_bess("bess1", BessSetpoint(500, 0, BessMode.PQ))
        asyncio.run(engine.step(30))
        history = engine.store.history()
        expected_wh = sum(item.bess[0].p_kw for item in history) * 1.0 / 3600 * 1000
        latest = engine.store.latest
        assert latest is not None
        assert latest.bess[0].energy.wh_positive == pytest.approx(expected_wh)
        assert latest.bess[0].energy_discharged_kwh == pytest.approx(expected_wh / 1000)
        assert latest.poi.energy_export_kwh + latest.poi.energy_import_kwh > 0

    def test_counters_hold_while_the_power_flow_fails(self) -> None:
        engine = make_engine(lambda topology: FlakySolver(topology, {3, 4}))
        engine.setpoints.set_bess("bess1", BessSetpoint(500, 0, BessMode.PQ))
        good = asyncio.run(engine.step(2))
        failed = asyncio.run(engine.step(2))
        assert not failed.converged
        assert failed.bess[0].energy == good.bess[0].energy

    def test_reset_starts_again_from_zero(self) -> None:
        engine = make_engine()
        engine.setpoints.set_bess("bess1", BessSetpoint(500, 0, BessMode.PQ))
        asyncio.run(engine.step(5))
        asyncio.run(engine.reset())
        snapshot = asyncio.run(engine.step(1))
        assert snapshot.bess[0].energy.wh_positive == pytest.approx(
            snapshot.bess[0].p_kw / 3600 * 1000
        )


def test_integrate_keys_every_device() -> None:
    engine = make_engine()
    snapshot = asyncio.run(engine.step(1))
    energy = integrate({}, snapshot, dt_s=1.0)
    assert set(energy) == {"poi.meter", "bess.bess1", "pv.pv1", "load.load1"}
    assert all(totals.day == snapshot.sim_time.date() for totals in energy.values())
