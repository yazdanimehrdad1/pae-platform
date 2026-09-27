"""One simulation step, as a pure function of (runtime, state, setpoints, step index).

No clock reads and no shared state: the engine passes everything in, which is what makes a run
deterministic for the same config, profiles, seed and setpoint sequence.

1. Sim time = start_time + step_index·step_s; read the PV availability and load profiles.
2. Apply the setpoints to the asset models (limits).
3. Set the network injections and solve.
4. Advance the SOCs with the actual power.
5. Return the new state and the snapshot.

If the power flow fails, the state isn't advanced and the snapshot repeats the last good values
with `converged = false`.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntFlag

import numpy as np

from powerflow.core.runtime import SiteRuntime
from powerflow.core.snapshot import (
    BessMeasurement,
    BusMeasurement,
    LoadMeasurement,
    PoiMeasurement,
    PvMeasurement,
    Snapshot,
    TransformerMeasurement,
)
from powerflow.errors import NonConvergenceError
from powerflow.models import bess as bess_model
from powerflow.models import pv as pv_model
from powerflow.models import status
from powerflow.models.common import apparent_power, power_factor
from powerflow.models.load import LoadOutput, load_output
from powerflow.network.solver import BusResult, Injection, NetworkResult
from powerflow.network.topology import (
    bess_aux_injection,
    bess_injection,
    load_injection,
    lv_bus,
    pv_injection,
    transformer_name,
)
from powerflow.site_config import POI_BUS_ID, PvAvailabilitySource

logger = logging.getLogger(__name__)
NO_VOLTAGE = BusResult(vn_kv=0.0, vm_pu=0.0, va_degree=0.0)
IRRADIANCE = PvAvailabilitySource.IRRADIANCE


@dataclass(frozen=True)
class Setpoints:
    bess: dict[str, bess_model.BessSetpoint]
    pv: dict[str, pv_model.PvSetpoint]


@dataclass(frozen=True)
class SimulationState:
    step_index: int
    bess: dict[str, bess_model.BessState]
    last_good: Snapshot | None = None


@dataclass(frozen=True)
class StepOutcome:
    state: SimulationState
    snapshot: Snapshot
    error: str | None = None


@dataclass(frozen=True)
class AssetOutputs:
    bess: dict[str, bess_model.BessOutput] = field(default_factory=dict)
    pv: dict[str, pv_model.PvOutput] = field(default_factory=dict)
    loads: dict[str, LoadOutput] = field(default_factory=dict)


def initial_state(runtime: SiteRuntime) -> SimulationState:
    return SimulationState(
        step_index=0,
        bess={
            asset_id: bess_model.BessState(soc_pct=asset.config.battery.soc_initial_pct)
            for asset_id, asset in runtime.bess.items()
        },
    )


def default_setpoints(runtime: SiteRuntime) -> Setpoints:
    """BESS idle at 0/0; PV uncurtailed at unity Q = 0."""
    return Setpoints(
        bess={asset_id: bess_model.BessSetpoint() for asset_id in runtime.bess},
        pv={
            asset_id: pv_model.PvSetpoint.unconstrained(asset.params)
            for asset_id, asset in runtime.pv.items()
        },
    )


def sim_time_at(runtime: SiteRuntime, step_index: int) -> datetime:
    simulation = runtime.config.simulation
    return simulation.start_time + timedelta(seconds=step_index * simulation.step_s)


def simulate_step(
    runtime: SiteRuntime, state: SimulationState, setpoints: Setpoints, step_index: int
) -> StepOutcome:
    """Advance from state.step_index to step_index (> state.step_index; a gap = skipped ticks,
    integrated as one longer step)."""
    if step_index <= state.step_index:
        raise ValueError(f"step_index {step_index} must be > {state.step_index}")
    simulation = runtime.config.simulation
    dt_s = (step_index - state.step_index) * simulation.step_s
    sim_time = sim_time_at(runtime, step_index)
    t_s = sim_time.timestamp()

    outputs = _dispatch_assets(runtime, state, setpoints, step_index, t_s, dt_s)
    try:
        network = runtime.solver.solve(_injections(outputs))
    except NonConvergenceError as error:
        logger.warning("step %d: power flow did not converge: %s", step_index, error)
        snapshot = _repeat_last_good(runtime, state, step_index, sim_time)
        new_state = SimulationState(step_index, state.bess, state.last_good)
        return StepOutcome(new_state, snapshot, str(error))

    new_bess = {
        asset_id: bess_model.integrate(
            runtime.bess[asset_id].params, state.bess[asset_id], output, dt_s
        )
        for asset_id, output in outputs.bess.items()
    }
    snapshot = build_snapshot(runtime, new_bess, outputs, network, step_index, sim_time, dt_s)
    return StepOutcome(SimulationState(step_index, new_bess, snapshot), snapshot)


def _dispatch_assets(
    runtime: SiteRuntime,
    state: SimulationState,
    setpoints: Setpoints,
    step_index: int,
    t_s: float,
    dt_s: float,
) -> AssetOutputs:
    outputs = AssetOutputs()
    for asset_id, asset in runtime.bess.items():
        outputs.bess[asset_id] = bess_model.dispatch(
            asset.params, state.bess[asset_id], setpoints.bess[asset_id], dt_s
        )
    for asset_id, asset in runtime.pv.items():
        column = "ghi_wm2" if asset.params.source is IRRADIANCE else "p_kw"
        available = pv_model.availability(asset.params, asset.profile.value_at(column, t_s))
        outputs.pv[asset_id] = pv_model.dispatch(asset.params, setpoints.pv[asset_id], available)
    # One generator per step, keyed on (seed, step): the same step always draws the same noise,
    # even when earlier steps were skipped.
    rng = np.random.default_rng((runtime.config.simulation.seed, step_index))
    for asset_id, asset in runtime.loads.items():
        values = asset.profile.values_at(t_s)
        outputs.loads[asset_id] = load_output(
            values["p_kw"], values["q_kvar"], asset.config.noise, rng
        )
    return outputs


def _injections(outputs: AssetOutputs) -> dict[str, Injection]:
    injections: dict[str, Injection] = {}
    for asset_id, output in outputs.bess.items():
        injections[bess_injection(asset_id)] = Injection(output.p_kw, output.q_kvar)
        injections[bess_aux_injection(asset_id)] = Injection(output.aux_p_kw, 0.0)
    for asset_id, output in outputs.pv.items():
        injections[pv_injection(asset_id)] = Injection(output.p_kw, output.q_kvar)
    for asset_id, output in outputs.loads.items():
        injections[load_injection(asset_id)] = Injection(output.p_kw, output.q_kvar)
    return injections


def _flag_names(flags: IntFlag) -> list[str]:
    """Names of the set bits, e.g. ["S_LIMIT", "RAMP_LIMIT"]."""
    return [member.name for member in type(flags) if member in flags and member.name]


def build_snapshot(
    runtime: SiteRuntime,
    bess_states: dict[str, bess_model.BessState],
    outputs: AssetOutputs,
    network: NetworkResult | None,
    step_index: int,
    sim_time: datetime,
    dt_s: float,
) -> Snapshot:
    """Assemble the snapshot. network=None (never converged yet) reports zero voltages."""

    def bus(name: str) -> BusResult:
        return network.buses[name] if network is not None else NO_VOLTAGE

    def transformer_loading(asset_id: str) -> float:
        if network is None:
            return 0.0
        result = network.transformers.get(transformer_name(asset_id))
        return result.loading_pct if result is not None else 0.0

    bess: list[BessMeasurement] = []
    for asset_id, output in outputs.bess.items():
        params = runtime.bess[asset_id].params
        soc_pct = bess_states[asset_id].soc_pct
        discharge_kwh, charge_kwh = bess_model.energy_available_kwh(params, soc_pct)
        discharge_kw, charge_kw = bess_model.p_available_kw(params, soc_pct, dt_s)
        terminal = bus(lv_bus(asset_id))
        operating_state = status.bess_operating_state(output)
        bess_alarms = status.bess_alarms(
            soc_pct,
            params.soc_min_pct,
            params.soc_max_pct,
            terminal.vm_pu,
            transformer_loading(asset_id),
        )
        bess.append(
            BessMeasurement(
                id=asset_id,
                p_cmd_kw=output.p_cmd_kw,
                q_cmd_kvar=output.q_cmd_kvar,
                p_kw=output.p_kw,
                q_kvar=output.q_kvar,
                s_kva=output.s_kva,
                soc_pct=soc_pct,
                energy_available_discharge_kwh=discharge_kwh,
                energy_available_charge_kwh=charge_kwh,
                p_available_discharge_kw=discharge_kw,
                p_available_charge_kw=charge_kw,
                status=int(output.status),
                status_name=output.status.name,
                limit_flags=int(output.flags),
                limit_flag_names=_flag_names(output.flags),
                aux_p_kw=output.aux_p_kw,
                v_lv_pu=terminal.vm_pu,
                v_lv_kv=terminal.v_kv,
                operating_state=int(operating_state),
                operating_state_name=operating_state.name,
                alarm_flags=int(bess_alarms),
                alarm_flag_names=_flag_names(bess_alarms),
            )
        )

    pv: list[PvMeasurement] = []
    for asset_id, output in outputs.pv.items():
        terminal = bus(lv_bus(asset_id))
        inverter_state = status.pv_inverter_state(output)
        pv_alarms = status.pv_alarms(terminal.vm_pu, transformer_loading(asset_id))
        pv.append(
            PvMeasurement(
                id=asset_id,
                p_available_kw=output.p_available_kw,
                p_limit_active_kw=output.p_limit_kw,
                p_kw=output.p_kw,
                q_kvar=output.q_kvar,
                s_kva=output.s_kva,
                pf=output.pf,
                curtailment_kw=output.curtailment_kw,
                irradiance_wm2=output.irradiance_wm2,
                status=int(output.status),
                status_name=output.status.name,
                limit_flags=int(output.flags),
                limit_flag_names=_flag_names(output.flags),
                v_lv_pu=terminal.vm_pu,
                v_lv_kv=terminal.v_kv,
                inverter_state=int(inverter_state),
                inverter_state_name=inverter_state.name,
                alarm_flags=int(pv_alarms),
                alarm_flag_names=_flag_names(pv_alarms),
            )
        )

    loads: list[LoadMeasurement] = []
    for asset_id, output in outputs.loads.items():
        injection_bus = next(
            spec.bus
            for spec in runtime.topology.injections
            if spec.name == load_injection(asset_id)
        )
        load_v_pu = bus(injection_bus).vm_pu
        supply_state = status.load_supply_state(load_v_pu)
        load_alarms = status.load_alarms(load_v_pu)
        loads.append(
            LoadMeasurement(
                id=asset_id,
                p_kw=output.p_kw,
                q_kvar=output.q_kvar,
                s_kva=output.s_kva,
                pf=output.pf,
                v_pu=load_v_pu,
                supply_state=int(supply_state),
                supply_state_name=supply_state.name,
                alarm_flags=int(load_alarms),
                alarm_flag_names=_flag_names(load_alarms),
            )
        )

    poi_bus = bus(POI_BUS_ID)
    p_kw = network.poi.p_kw if network is not None else 0.0
    q_kvar = network.poi.q_kvar if network is not None else 0.0
    poi_s_kva, poi_pf = apparent_power(p_kw, q_kvar), power_factor(p_kw, q_kvar)
    meter = status.meter_state(converged=network is not None)
    meter_alarms = status.meter_alarms(p_kw, poi_bus.vm_pu, poi_pf, poi_s_kva)
    poi = PoiMeasurement(
        p_kw=p_kw,
        q_kvar=q_kvar,
        s_kva=poi_s_kva,
        pf=poi_pf,
        v_kv=poi_bus.v_kv,
        v_pu=poi_bus.vm_pu,
        angle_deg=poi_bus.va_degree,
        i_a=network.poi.i_a if network is not None else 0.0,
        p_loss_total_kw=network.site_p_loss_kw if network is not None else 0.0,
        q_loss_total_kvar=network.site_q_loss_kvar if network is not None else 0.0,
        meter_state=int(meter),
        meter_state_name=meter.name,
        alarm_flags=int(meter_alarms),
        alarm_flag_names=_flag_names(meter_alarms),
    )
    buses = [
        BusMeasurement(
            name=spec.name,
            vn_kv=spec.vn_kv,
            v_kv=bus(spec.name).v_kv,
            v_pu=bus(spec.name).vm_pu,
            angle_deg=bus(spec.name).va_degree,
        )
        for spec in runtime.topology.buses
    ]
    transformers = []
    if network is not None:
        transformers = [
            TransformerMeasurement(
                name=name,
                p_hv_kw=result.p_hv_kw,
                q_hv_kvar=result.q_hv_kvar,
                p_lv_kw=result.p_lv_kw,
                q_lv_kvar=result.q_lv_kvar,
                p_loss_kw=result.p_loss_kw,
                q_loss_kvar=result.q_loss_kvar,
                loading_pct=result.loading_pct,
            )
            for name, result in network.transformers.items()
        ]
    return Snapshot(
        step_id=step_index,
        sim_time=sim_time,
        converged=network is not None,
        poi=poi,
        buses=buses,
        transformers=transformers,
        bess=bess,
        pv=pv,
        loads=loads,
    )


def _repeat_last_good(
    runtime: SiteRuntime, state: SimulationState, step_index: int, sim_time: datetime
) -> Snapshot:
    if state.last_good is not None:
        stale = status.MeterState.STALE
        poi = state.last_good.poi.model_copy(
            update={"meter_state": int(stale), "meter_state_name": stale.name}
        )
        return state.last_good.model_copy(
            update={"step_id": step_index, "sim_time": sim_time, "converged": False, "poi": poi}
        )
    # Never converged: report the idle asset state with no network values.
    idle = AssetOutputs(
        bess={
            asset_id: bess_model.BessOutput(
                0.0, 0.0, 0.0, 0.0, bess_model.BessFlag.NONE, bess_model.BessStatus.IDLE, 0.0
            )
            for asset_id in runtime.bess
        },
        pv={
            asset_id: pv_model.PvOutput(
                0.0,
                asset.params.p_max_kw,
                0.0,
                0.0,
                pv_model.PvFlag.NONE,
                pv_model.PvStatus.OFF,
                0.0,
            )
            for asset_id, asset in runtime.pv.items()
        },
        loads={asset_id: LoadOutput(0.0, 0.0) for asset_id in runtime.loads},
    )
    step_s = runtime.config.simulation.step_s
    return build_snapshot(runtime, state.bess, idle, None, step_index, sim_time, step_s)
