"""BESS model: SOC integration, efficiencies, SOC limits, S circle, ramp, modes."""

import math
from dataclasses import replace

import pytest

from powerflow.models.bess import (
    BessFlag,
    BessMode,
    BessParams,
    BessSetpoint,
    BessState,
    BessStatus,
    dispatch,
    energy_available_kwh,
    integrate,
)
from powerflow.site_config import Priority

PARAMS = BessParams(
    p_discharge_max_kw=2500,
    p_charge_max_kw=2000,
    s_rated_kva=2750,
    capacity_kwh=10000,
    soc_min_pct=5,
    soc_max_pct=95,
    eta_charge=0.95,
    eta_discharge=0.9,
    ramp_kw_per_s=None,
    priority=Priority.P,
    aux_load_kw=10,
)
HOUR_S = 3600.0


def pq(p_kw: float, q_kvar: float = 0.0) -> BessSetpoint:
    return BessSetpoint(p_kw=p_kw, q_kvar=q_kvar, mode=BessMode.PQ)


def step(params: BessParams, state: BessState, setpoint: BessSetpoint, dt_s: float) -> BessState:
    return integrate(params, state, dispatch(params, state, setpoint, dt_s), dt_s)


class TestSocIntegration:
    def test_discharge_draws_p_over_eta(self) -> None:
        # 1000 kW for 1 h at η_d = 0.9: 1111.1 kWh from the cells = 11.11 % of 10 MWh.
        state = step(PARAMS, BessState(soc_pct=50), pq(1000), HOUR_S)
        assert state.soc_pct == pytest.approx(50 - 1000 / 0.9 / 10000 * 100)

    def test_charge_stores_p_times_eta(self) -> None:
        state = step(PARAMS, BessState(soc_pct=50), pq(-1000), HOUR_S)
        assert state.soc_pct == pytest.approx(50 + 1000 * 0.95 / 10000 * 100)

    def test_many_small_steps_equal_one_big_step(self) -> None:
        state = BessState(soc_pct=50)
        for _ in range(3600):
            state = step(PARAMS, state, pq(1000), 1.0)
        assert state.soc_pct == pytest.approx(50 - 1000 / 0.9 / 10000 * 100)

    def test_idle_and_offline_hold_soc(self) -> None:
        for mode in (BessMode.IDLE, BessMode.OFFLINE):
            state = step(PARAMS, BessState(soc_pct=50), BessSetpoint(2000, 0, mode), HOUR_S)
            assert state.soc_pct == 50


class TestSocLimits:
    def test_discharge_lands_exactly_on_soc_min(self) -> None:
        # 0.5 % above min = 50 kWh in the cells = 45 kWh AC; asking 2500 kW for 60 s would be
        # 41.7 kWh, fine; for 120 s it'd be 83 kWh, so P is limited to 45 kWh / 120 s.
        state = BessState(soc_pct=5.5)
        output = dispatch(PARAMS, state, pq(2500), 120)
        assert output.flags & BessFlag.SOC_LIMIT
        assert output.p_kw == pytest.approx(45 / (120 / HOUR_S))
        assert integrate(PARAMS, state, output, 120).soc_pct == pytest.approx(5)

    def test_no_discharge_at_soc_min(self) -> None:
        output = dispatch(PARAMS, BessState(soc_pct=5), pq(1000), 1)
        assert output.p_kw == 0 and output.flags & BessFlag.SOC_LIMIT

    def test_no_charge_at_soc_max(self) -> None:
        output = dispatch(PARAMS, BessState(soc_pct=95), pq(-1000), 1)
        assert output.p_kw == 0 and output.flags & BessFlag.SOC_LIMIT

    def test_charge_allowed_at_soc_min(self) -> None:
        output = dispatch(PARAMS, BessState(soc_pct=5), pq(-1000), 1)
        assert output.p_kw == -1000 and output.flags == BessFlag.NONE

    def test_soc_never_leaves_limits_over_a_long_run(self) -> None:
        state = BessState(soc_pct=50)
        for index in range(20_000):
            setpoint = pq(2500 if (index // 5000) % 2 == 0 else -2000)
            state = step(PARAMS, state, setpoint, 10)
            assert PARAMS.soc_min_pct <= state.soc_pct <= PARAMS.soc_max_pct

    def test_energy_available(self) -> None:
        discharge_kwh, charge_kwh = energy_available_kwh(PARAMS, 50)
        assert discharge_kwh == pytest.approx(4500 * 0.9)
        assert charge_kwh == pytest.approx(4500 / 0.95)


class TestLimits:
    def test_p_rating(self) -> None:
        output = dispatch(PARAMS, BessState(soc_pct=50), pq(3000), 1)
        assert output.p_kw == 2500 and output.flags & BessFlag.P_LIMIT
        output = dispatch(PARAMS, BessState(soc_pct=50), pq(-3000), 1)
        assert output.p_kw == -2000 and output.flags & BessFlag.P_LIMIT

    def test_s_circle_p_priority_keeps_p(self) -> None:
        output = dispatch(PARAMS, BessState(soc_pct=50), pq(2500, 2000), 1)
        assert output.p_kw == 2500
        assert output.q_kvar == pytest.approx(math.sqrt(2750**2 - 2500**2))
        assert output.flags & BessFlag.S_LIMIT
        assert output.s_kva == pytest.approx(2750)

    def test_s_circle_q_priority_keeps_q(self) -> None:
        params = replace(PARAMS, priority=Priority.Q)
        output = dispatch(params, BessState(soc_pct=50), pq(-2000, -2500), 1)
        assert output.q_kvar == -2500
        assert output.p_kw == pytest.approx(-math.sqrt(2750**2 - 2500**2))
        assert output.flags & BessFlag.S_LIMIT

    def test_ramp_limits_p_change_per_step(self) -> None:
        params = replace(PARAMS, ramp_kw_per_s=100)
        state = BessState(soc_pct=50)
        powers = []
        for _ in range(12):
            output = dispatch(params, state, pq(1000), 1)
            powers.append(output.p_kw)
            state = integrate(params, state, output, 1)
        assert powers[:10] == pytest.approx([100 * (index + 1) for index in range(10)])
        assert powers[10:] == [1000, 1000]
        # Only the ramping steps are flagged.
        assert dispatch(params, BessState(50), pq(1000), 1).flags & BessFlag.RAMP_LIMIT
        assert not dispatch(params, state, pq(1000), 1).flags & BessFlag.RAMP_LIMIT

    def test_ramp_scales_with_dt(self) -> None:
        params = replace(PARAMS, ramp_kw_per_s=100)
        assert dispatch(params, BessState(soc_pct=50), pq(1000), 5).p_kw == 500

    def test_soc_limit_beats_ramp(self) -> None:
        params = replace(PARAMS, ramp_kw_per_s=1)
        state = BessState(soc_pct=5, p_kw=2000)
        output = dispatch(params, state, pq(2000), 1)
        assert output.p_kw == 0 and output.flags & BessFlag.SOC_LIMIT

    def test_q_trimmed_after_ramp_keeps_s(self) -> None:
        # Q priority: ramping P down from 2500 leaves P high, so Q (not P) gives way.
        params = replace(PARAMS, priority=Priority.Q, ramp_kw_per_s=100)
        state = BessState(soc_pct=50, p_kw=2500)
        output = dispatch(params, state, pq(0, 2750), 1)
        assert output.p_kw == 2400
        assert math.hypot(output.p_kw, output.q_kvar) == pytest.approx(2750)
        assert output.flags & BessFlag.RAMP_LIMIT and output.flags & BessFlag.S_LIMIT


class TestModes:
    def test_offline_forces_zero_at_once(self) -> None:
        params = replace(PARAMS, ramp_kw_per_s=10)
        output = dispatch(
            params, BessState(50, p_kw=2000), BessSetpoint(1000, 0, BessMode.OFFLINE), 1
        )
        assert (output.p_kw, output.q_kvar, output.status) == (0, 0, BessStatus.OFFLINE)
        assert output.aux_p_kw == 10

    def test_idle_ramps_to_zero(self) -> None:
        params = replace(PARAMS, ramp_kw_per_s=500)
        output = dispatch(params, BessState(50, p_kw=2000), BessSetpoint(1000, 0, BessMode.IDLE), 1)
        assert output.p_kw == 1500 and output.status == BessStatus.IDLE
        assert (output.p_cmd_kw, output.q_cmd_kvar) == (0, 0)

    def test_pq_reports_commanded_and_actual(self) -> None:
        output = dispatch(PARAMS, BessState(50), pq(3000, 100), 1)
        assert output.status == BessStatus.RUNNING
        assert (output.p_cmd_kw, output.q_cmd_kvar) == (2500, 100)
        assert (output.p_kw, output.q_kvar) == (2500, 100)
