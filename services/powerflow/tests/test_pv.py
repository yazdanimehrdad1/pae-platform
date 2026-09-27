"""PV model: clipping, curtailment, Q and power factor control, irradiance source."""

import math
from dataclasses import replace

import pytest

from powerflow.models.pv import (
    PvFlag,
    PvParams,
    PvQMode,
    PvSetpoint,
    PvStatus,
    availability,
    dispatch,
)
from powerflow.site_config import Priority, PvAvailabilitySource

PARAMS = PvParams(
    dc_kwp=6500,
    p_max_kw=5000,
    s_rated_kva=5500,
    loss_factor=0.0,
    priority=Priority.P,
    source=PvAvailabilitySource.AC_KW,
)
FREE = PvSetpoint(p_limit_kw=5000)


def test_clipping_at_inverter_p_max() -> None:
    available = availability(PARAMS, 5300)
    assert available.p_available_kw == 5000 and available.clipped
    output = dispatch(PARAMS, FREE, available)
    assert output.p_kw == 5000 and output.flags & PvFlag.CLIPPED
    assert output.status == PvStatus.PRODUCING


def test_loss_factor_applies_before_clipping() -> None:
    params = replace(PARAMS, loss_factor=0.1)
    assert availability(params, 4000).p_available_kw == pytest.approx(3600)
    assert availability(params, 6000).p_available_kw == 5000


def test_irradiance_source() -> None:
    params = replace(PARAMS, source=PvAvailabilitySource.IRRADIANCE, loss_factor=0.05)
    # 6500 kWp · 500/1000 · 0.95 = 3087.5 kW
    available = availability(params, 500)
    assert available.p_available_kw == pytest.approx(3087.5)
    assert available.irradiance_wm2 == 500
    assert availability(params, 1000).p_available_kw == 5000  # 6175 kW clipped


def test_curtailment_in_kw() -> None:
    output = dispatch(PARAMS, PvSetpoint(p_limit_kw=2000), availability(PARAMS, 4000))
    assert output.p_kw == 2000
    assert output.curtailment_kw == 2000
    assert output.flags & PvFlag.CURTAILED and output.status == PvStatus.CURTAILED


def test_curtailment_above_available_does_nothing() -> None:
    output = dispatch(PARAMS, PvSetpoint(p_limit_kw=4500), availability(PARAMS, 4000))
    assert output.p_kw == 4000 and output.curtailment_kw == 0
    assert output.status == PvStatus.PRODUCING


def test_night_is_off() -> None:
    output = dispatch(PARAMS, FREE, availability(PARAMS, 0))
    assert output.p_kw == 0 and output.status == PvStatus.OFF


def test_q_setpoint_with_p_priority_trims_q() -> None:
    output = dispatch(PARAMS, PvSetpoint(5000, PvQMode.Q, q_kvar=-4000), availability(PARAMS, 5000))
    assert output.p_kw == 5000
    assert output.q_kvar == pytest.approx(-math.sqrt(5500**2 - 5000**2))
    assert output.flags & PvFlag.S_LIMIT


def test_q_setpoint_with_q_priority_trims_p() -> None:
    params = replace(PARAMS, priority=Priority.Q)
    output = dispatch(params, PvSetpoint(5000, PvQMode.Q, q_kvar=3000), availability(params, 5000))
    assert output.q_kvar == 3000
    assert output.p_kw == pytest.approx(math.sqrt(5500**2 - 3000**2))


@pytest.mark.parametrize("pf", [0.95, -0.9, 1.0])
def test_power_factor_setpoint_holds_pf(pf: float) -> None:
    output = dispatch(PARAMS, PvSetpoint(5000, PvQMode.PF, pf=pf), availability(PARAMS, 3000))
    assert output.p_kw == 3000
    assert output.pf == pytest.approx(pf)


def test_power_factor_scales_both_at_s_limit() -> None:
    output = dispatch(PARAMS, PvSetpoint(5000, PvQMode.PF, pf=0.8), availability(PARAMS, 5000))
    assert output.s_kva == pytest.approx(5500)
    assert output.pf == pytest.approx(0.8)
    assert output.flags & PvFlag.S_LIMIT
