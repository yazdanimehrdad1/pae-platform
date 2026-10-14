"""Injected conditions as pure functions (validate, apply, summary), and their effect on the
simulation through the engine: faults, breakers, comm loss and grid events."""

import asyncio
from typing import Any

import pytest
from conftest import PROFILES, make_site_config, site_config_dict

from powerflow.conditions import (
    CATALOG,
    AlarmResetChange,
    AssetFault,
    AssetFaultChange,
    BreakerChange,
    CommLossChange,
    CommTarget,
    Conditions,
    FaultCause,
    FaultClock,
    GridFrequencyChange,
    GridVoltageChange,
    Severity,
    apply_change,
    expire_faults,
    initial_conditions,
    reset_alarms,
    summary,
    validate_change,
)
from powerflow.conditions.fault_catalog import SEVERITY
from powerflow.conditions.models import restore_step
from powerflow.core.engine import Engine
from powerflow.core.runtime import SiteRuntime
from powerflow.core.snapshot import Snapshot
from powerflow.errors import ConditionError, UnknownAssetError
from powerflow.models.bess import BessFlag, BessMode, BessSetpoint, BessStatus
from powerflow.models.pv import PvFlag, PvStatus
from powerflow.models.status import (
    BessAlarm,
    BessOperatingState,
    BreakerState,
    LoadAlarm,
    LoadSupplyState,
    MeterState,
    PvAlarm,
    PvInverterState,
)
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.site_config import SiteConfig


class TestPureFunctions:
    def test_initial_conditions_follow_the_config_breakers(self) -> None:
        raw = site_config_dict(n_bess=2)
        raw["bess"][1]["breaker"] = {"closed": False}
        raw["poi"] = {"breaker": {"closed": False}}
        conditions = initial_conditions(SiteConfig.model_validate(raw))
        assert conditions.open_breakers == {"bess2", "poi"}
        assert not conditions.faults and not conditions.comm_loss

    def test_apply_and_clear_each_kind(self) -> None:
        conditions = Conditions()
        conditions = apply_change(conditions, BreakerChange(breaker="pv1", closed=False), 5)
        conditions = apply_change(
            conditions, AssetFaultChange(asset_id="bess1", cause=FaultCause.OVER_TEMPERATURE), 5
        )
        conditions = apply_change(conditions, CommLossChange(target=CommTarget.POI_METER), 5)
        conditions = apply_change(conditions, GridVoltageChange(vm_pu=0.9), 5)
        conditions = apply_change(conditions, GridFrequencyChange(hz=59.5), 5)
        assert conditions.open_breakers == {"pv1"}
        assert conditions.faults == {"bess1": {FaultCause.OVER_TEMPERATURE: AssetFault(5)}}
        assert conditions.comm_lost(CommTarget.POI_METER)
        assert (conditions.grid_vm_pu, conditions.grid_hz) == (0.9, 59.5)

        conditions = apply_change(conditions, BreakerChange(breaker="pv1", closed=True), 6)
        conditions = apply_change(conditions, AssetFaultChange(asset_id="bess1", active=False), 6)
        conditions = apply_change(
            conditions, CommLossChange(target=CommTarget.POI_METER, active=False), 6
        )
        conditions = apply_change(conditions, GridVoltageChange(vm_pu=None), 6)
        latched = {"bess1": {FaultCause.OVER_TEMPERATURE: AssetFault(5, latched=True)}}
        assert conditions == Conditions(faults=latched, grid_hz=59.5)  # the fault latched
        conditions = apply_change(conditions, AlarmResetChange(asset_id="bess1"), 7)
        assert conditions == Conditions(grid_hz=59.5)

    def test_comm_loss_keeps_the_step_it_began(self) -> None:
        change = CommLossChange(target=CommTarget.ASSET, id="bess1")
        conditions = apply_change(Conditions(), change, 3)
        conditions = apply_change(conditions, change, 9)  # already lost: unchanged
        assert conditions.comm_loss == {(CommTarget.ASSET, "bess1"): 3}

    @pytest.mark.parametrize(
        ("change", "error"),
        [
            (BreakerChange(breaker="nope", closed=False), UnknownAssetError),
            (AssetFaultChange(asset_id="nope"), UnknownAssetError),
            (AssetFaultChange(asset_id="load1"), ConditionError),
            (
                AssetFaultChange(asset_id="bess1", cause=FaultCause.BLOWN_STRING_FUSE),
                ConditionError,
            ),
            (AssetFaultChange(asset_id="pv1", cause=FaultCause.FAN_ERROR), ConditionError),
            (AlarmResetChange(asset_id="load1"), ConditionError),
            (AlarmResetChange(asset_id="nope"), UnknownAssetError),
            (CommLossChange(target=CommTarget.ASSET, id="nope"), UnknownAssetError),
            (CommLossChange(target=CommTarget.METER, id="nope"), UnknownAssetError),
            (CommLossChange(target=CommTarget.POI_METER, id="x"), ConditionError),
        ],
    )
    def test_validation(self, change: Any, error: type[Exception]) -> None:
        with pytest.raises(error):
            validate_change(change, make_site_config())

    def test_valid_changes_pass(self) -> None:
        config = make_site_config()
        for change in (
            BreakerChange(breaker="poi", closed=False),
            BreakerChange(breaker="load1", closed=False),
            AssetFaultChange(asset_id="pv1", cause=FaultCause.DC_OVERVOLTAGE),
            CommLossChange(target=CommTarget.ASSET, id="load1"),
            CommLossChange(target=CommTarget.POI_METER),
        ):
            validate_change(change, config)

    def test_stored_changes_from_before_the_catalog_still_validate(self) -> None:
        """Stored scenarios carry `cause` even on a clear, and no `auto_restore`."""
        config = make_site_config()
        for raw in (
            {"type": "asset_fault", "asset_id": "bess1", "active": True, "cause": "trip"},
            {"type": "asset_fault", "asset_id": "bess1", "active": False, "cause": "trip"},
            {"type": "asset_fault", "asset_id": "pv1", "active": True, "cause": "ground_fault"},
            # a clear ignores the cause, even one the asset can't have
            {"type": "asset_fault", "asset_id": "pv1", "active": False, "cause": "fan_error"},
        ):
            change = AssetFaultChange.model_validate(raw)
            assert change.auto_restore is False
            validate_change(change, config)

    def test_summary_lists_every_breaker(self) -> None:
        config = make_site_config()
        report = summary(Conditions(open_breakers=frozenset({"bess1"})), config)
        assert [(item.id, item.kind, item.closed) for item in report.breakers] == [
            ("poi", "poi", True),
            ("bess1", "bess", False),
            ("pv1", "pv", True),
            ("load1", "load", True),
        ]

    def test_poi_is_a_reserved_asset_id(self) -> None:
        raw = site_config_dict()
        raw["bess"][0]["id"] = "poi"
        with pytest.raises(ValueError, match="reserved"):
            SiteConfig.model_validate(raw)


class TestFaultLifecycle:
    """Latching, alarm reset, auto-restore, warnings and several causes per asset (pure)."""

    def test_clear_latches_faults_and_drops_warnings(self) -> None:
        conditions = Conditions()
        for cause in (FaultCause.FAN_ERROR, FaultCause.OVER_TEMPERATURE):
            change = AssetFaultChange(asset_id="bess1", cause=cause)
            conditions = apply_change(conditions, change, 2)
        assert conditions.tripped("bess1")
        assert conditions.asserted_causes("bess", "bess1") == [
            FaultCause.OVER_TEMPERATURE,  # catalog order: faults before warnings
            FaultCause.FAN_ERROR,
        ]
        conditions = apply_change(conditions, AssetFaultChange(asset_id="bess1", active=False), 4)
        latched = AssetFault(2, None, latched=True)
        assert conditions.faults == {"bess1": {FaultCause.OVER_TEMPERATURE: latched}}
        assert conditions.tripped("bess1")  # still, until a reset

    def test_reset_drops_only_latched_faults(self) -> None:
        conditions = apply_change(Conditions(), AssetFaultChange(asset_id="pv1"), 1)
        assert reset_alarms(conditions, "pv1") == conditions  # the cause is still injected
        conditions = apply_change(conditions, AssetFaultChange(asset_id="pv1", active=False), 2)
        conditions = apply_change(
            conditions, AssetFaultChange(asset_id="pv1", cause=FaultCause.GROUND_FAULT), 3
        )
        conditions = reset_alarms(conditions, "pv1")
        assert conditions.faults == {"pv1": {FaultCause.GROUND_FAULT: AssetFault(3)}}

    def test_warning_never_trips_and_derates(self) -> None:
        conditions = apply_change(
            Conditions(), AssetFaultChange(asset_id="pv1", cause=FaultCause.BLOWN_STRING_FUSE), 0
        )
        assert not conditions.tripped("pv1")
        assert conditions.p_available_factor("pv", "pv1") == pytest.approx(0.9)
        assert conditions.p_max_factor("pv", "pv1") == 1.0
        conditions = apply_change(
            conditions,
            AssetFaultChange(asset_id="pv1", cause=FaultCause.OVER_TEMPERATURE_WARNING),
            0,
        )
        assert conditions.p_max_factor("pv", "pv1") == pytest.approx(0.5)

    def test_auto_restore_is_two_to_ten_minutes_and_reproducible(self) -> None:
        for step_s in (1.0, 10.0):
            clock = FaultClock(seed=3, step_s=step_s)
            for since in range(20):
                restore = restore_step(clock, "bess1", FaultCause.TRIP, since)
                assert 120 / step_s <= restore - since <= 600 / step_s + 1
                assert restore == restore_step(clock, "bess1", FaultCause.TRIP, since)
        draws = {restore_step(FaultClock(seed), "bess1", FaultCause.TRIP, 0) for seed in range(8)}
        assert len(draws) > 1  # the seed matters

    def test_auto_restore_expires_and_never_latches(self) -> None:
        change = AssetFaultChange(asset_id="bess1", auto_restore=True)
        conditions = apply_change(Conditions(), change, 10, FaultClock(seed=1))
        restore = conditions.faults["bess1"][FaultCause.TRIP].restore_step
        assert restore is not None
        assert expire_faults(conditions, restore - 1) == conditions
        assert expire_faults(conditions, restore + 50) == Conditions()  # a gap still expires it
        cleared = apply_change(conditions, AssetFaultChange(asset_id="bess1", active=False), 11)
        assert cleared == Conditions()  # cleared early: gone, not latched

    def test_summary_reports_each_cause(self) -> None:
        config = make_site_config()
        change = AssetFaultChange(asset_id="bess1", auto_restore=True)
        conditions = apply_change(Conditions(), change, 0, FaultClock(seed=3))
        origin = config.simulation.start_time
        assert not isinstance(origin, str)
        (fault,) = summary(conditions, config, origin).faults
        assert fault.severity is Severity.FAULT and fault.auto_restore and not fault.latched
        assert fault.restore_step is not None and fault.restore_sim_time is not None
        elapsed_s = (fault.restore_sim_time - origin).total_seconds()
        assert elapsed_s == fault.restore_step * config.simulation.step_s


class TestCatalog:
    def test_a_cause_has_one_severity(self) -> None:
        for spec in CATALOG:
            assert SEVERITY[spec.cause] is spec.severity

    def test_no_silent_fault(self) -> None:
        for spec in CATALOG:
            if spec.severity is Severity.FAULT:
                assert spec.alrm or spec.evt1, f"{spec.kind} {spec.cause} sets no bit"
                assert spec.kind == "bess" or spec.fault_code > 0
            else:
                assert min(spec.p_max_factor, spec.p_available_factor) < 1

    def test_pv_has_no_battery_events(self) -> None:
        assert not any(spec.evt1 for spec in CATALOG if spec.kind == "pv")


def make_engine(raw: dict[str, Any] | None = None) -> Engine:
    config = SiteConfig.model_validate(raw or site_config_dict())
    return Engine(SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES)


def step(engine: Engine, count: int = 1) -> Snapshot:
    return asyncio.run(engine.step(count))


def metered(raw: dict[str, Any]) -> dict[str, Any]:
    raw["meters"] = [{"id": "m_bess1", "transformer": "bess1"}]
    return raw


class TestFaults:
    def test_bess_fault_latches_until_an_alarm_reset(self) -> None:
        engine = make_engine()
        engine.setpoints.set_bess("bess1", BessSetpoint(1000, 0, BessMode.PQ))
        before = step(engine).bess[0]
        assert before.p_kw == pytest.approx(1000)
        engine.apply_condition(
            AssetFaultChange(asset_id="bess1", cause=FaultCause.OVER_TEMPERATURE)
        )
        faulted = step(engine).bess[0]
        assert faulted.p_kw == 0 and faulted.status == BessStatus.FAULT
        assert faulted.operating_state == BessOperatingState.FAULT
        assert faulted.alarm_flags & BessAlarm.OVER_TEMPERATURE
        assert faulted.fault_causes == [FaultCause.OVER_TEMPERATURE]
        assert faulted.soc_pct == step(engine).bess[0].soc_pct  # held
        engine.apply_condition(AssetFaultChange(asset_id="bess1", active=False))
        latched = step(engine).bess[0]
        assert latched.status == BessStatus.FAULT  # the cause is gone, the alarm is not
        assert latched.fault_causes == [FaultCause.OVER_TEMPERATURE]
        assert engine.reset_alarms("bess1") == [FaultCause.OVER_TEMPERATURE]
        recovered = step(engine).bess[0]
        assert recovered.p_kw > 0 and not recovered.fault_causes  # back on its setpoint

    def test_reset_while_the_cause_is_active_does_nothing(self) -> None:
        engine = make_engine()
        engine.apply_condition(AssetFaultChange(asset_id="bess1"))
        assert engine.reset_alarms("bess1") == []
        assert step(engine).bess[0].status == BessStatus.FAULT

    def test_auto_restore_clears_itself(self) -> None:
        raw = site_config_dict()
        raw["simulation"]["step_s"] = 60  # 2-10 min = 2-10 steps
        engine = make_engine(raw)
        engine.setpoints.set_bess("bess1", BessSetpoint(500, 0, BessMode.PQ))
        report = engine.apply_condition(AssetFaultChange(asset_id="bess1", auto_restore=True))
        restore = report.faults[0].restore_step
        assert restore is not None and 2 <= restore <= 11
        assert step(engine, restore - 1).bess[0].status == BessStatus.FAULT
        assert step(engine).bess[0].status == BessStatus.RUNNING
        assert not engine.active_conditions().faults

    def test_warning_derates_without_tripping(self) -> None:
        engine = make_engine()
        engine.setpoints.set_bess("bess1", BessSetpoint(2500, 0, BessMode.PQ))
        engine.apply_condition(AssetFaultChange(asset_id="bess1", cause=FaultCause.FAN_ERROR))
        derated = step(engine).bess[0]
        assert derated.status == BessStatus.RUNNING
        assert derated.p_kw == pytest.approx(0.7 * 2500)
        assert derated.limit_flags & BessFlag.DERATED
        assert derated.p_available_discharge_kw == pytest.approx(0.7 * 2500)
        engine.apply_condition(AssetFaultChange(asset_id="bess1", active=False))  # no latch
        assert step(engine).bess[0].p_kw == pytest.approx(2500)

    def test_blown_string_fuse_loses_part_of_the_array(self) -> None:
        reference = step(make_engine()).pv[0].p_available_kw
        engine = make_engine()
        engine.apply_condition(AssetFaultChange(asset_id="pv1", cause=FaultCause.BLOWN_STRING_FUSE))
        pv = step(engine).pv[0]
        assert pv.p_available_kw == pytest.approx(0.9 * reference)
        assert pv.status != PvStatus.FAULT and pv.limit_flags & PvFlag.DERATED

    def test_clear_all_drops_latched_faults(self) -> None:
        engine = make_engine()
        engine.apply_condition(AssetFaultChange(asset_id="pv1"))
        engine.apply_condition(AssetFaultChange(asset_id="pv1", active=False))
        assert engine.active_conditions().faults[0].latched
        assert not engine.clear_conditions().faults
        assert step(engine).pv[0].status != PvStatus.FAULT

    def test_comm_loss_hides_a_new_fault(self) -> None:
        engine = make_engine()
        step(engine)
        engine.apply_condition(CommLossChange(target=CommTarget.ASSET, id="bess1"))
        engine.apply_condition(AssetFaultChange(asset_id="bess1"))
        snapshot = step(engine)
        assert not snapshot.bess[0].fault_causes  # frozen: published before the fault
        assert snapshot.bess[0].status != BessStatus.FAULT
        assert snapshot.conditions is not None and snapshot.conditions.faults  # the truth

    def test_pv_fault_reports_its_cause(self) -> None:
        engine = make_engine()
        engine.apply_condition(AssetFaultChange(asset_id="pv1", cause=FaultCause.GROUND_FAULT))
        pv = step(engine).pv[0]
        assert pv.p_kw == 0 and pv.p_available_kw > 0
        assert pv.status == PvStatus.FAULT and pv.inverter_state == PvInverterState.FAULT
        assert pv.alarm_flags & PvAlarm.GROUND_FAULT


class TestBreakers:
    def test_asset_breaker_takes_it_offline(self) -> None:
        engine = make_engine(metered(site_config_dict()))
        engine.setpoints.set_bess("bess1", BessSetpoint(1000, 0, BessMode.PQ))
        engine.apply_condition(BreakerChange(breaker="bess1", closed=False))
        snapshot = step(engine)
        bess = snapshot.bess[0]
        assert snapshot.converged
        assert bess.status == BessStatus.OFFLINE and bess.p_kw == 0 and bess.v_lv_pu == 0
        assert bess.breaker_state == BreakerState.OPEN and bess.breaker_state_name == "OPEN"
        assert snapshot.meters[0].p_kw == 0  # the feeder meter sees nothing through it
        assert snapshot.pv[0].p_kw > 0  # the rest of the site carries on

    def test_poi_breaker_de_energises_the_site(self) -> None:
        engine = make_engine()
        step(engine)
        engine.apply_condition(BreakerChange(breaker="poi", closed=False))
        snapshot = step(engine)
        assert snapshot.converged
        assert snapshot.poi.p_kw == 0 and snapshot.poi.v_pu == 0 and snapshot.poi.hz == 0
        assert snapshot.poi.breaker_state == BreakerState.OPEN
        assert snapshot.pv[0].status == PvStatus.OFFLINE
        assert snapshot.loads[0].supply_state == LoadSupplyState.DE_ENERGIZED
        assert snapshot.loads[0].p_kw == 0
        energy = snapshot.poi.energy
        assert step(engine).poi.energy.wh_negative == energy.wh_negative  # nothing flows
        engine.apply_condition(BreakerChange(breaker="poi", closed=True))
        assert step(engine).poi.v_pu > 0.9  # recloses and converges

    def test_open_load_keeps_other_loads_noise(self) -> None:
        raw = site_config_dict(n_loads=2)
        for load in raw["loads"]:
            load["noise"] = {"p_std_pct": 5}
        reference = step(make_engine(raw)).loads[1].p_kw
        engine = make_engine(raw)
        engine.apply_condition(BreakerChange(breaker="load1", closed=False))
        snapshot = step(engine)
        assert snapshot.loads[0].p_kw == 0
        assert snapshot.loads[0].supply_state == LoadSupplyState.DE_ENERGIZED
        assert snapshot.loads[1].p_kw == pytest.approx(reference)

    def test_config_breaker_position_applies_at_start_and_reset(self) -> None:
        raw = site_config_dict()
        raw["pv"][0]["breaker"] = {"closed": False}
        engine = make_engine(raw)
        assert step(engine).pv[0].status == PvStatus.OFFLINE
        engine.apply_condition(BreakerChange(breaker="pv1", closed=True))
        assert step(engine).pv[0].p_kw > 0
        asyncio.run(engine.reset())
        assert step(engine).pv[0].status == PvStatus.OFFLINE


class TestCommLoss:
    def test_frozen_values_then_a_jump(self) -> None:
        engine = make_engine()
        engine.setpoints.set_bess("bess1", BessSetpoint(500, 0, BessMode.PQ))
        step(engine)
        engine.apply_condition(CommLossChange(target=CommTarget.ASSET, id="bess1"))
        engine.setpoints.set_bess("bess1", BessSetpoint(1500, 0, BessMode.PQ))
        frozen = step(engine, 3).bess[0]
        assert frozen.p_kw == pytest.approx(500) and frozen.alarm_flags & BessAlarm.COMM_LOSS
        assert engine.store.latest is not None and engine.store.latest.bess[0].p_kw == 500
        engine.apply_condition(CommLossChange(target=CommTarget.ASSET, id="bess1", active=False))
        live = step(engine).bess[0]
        assert live.p_kw == pytest.approx(1500) and not live.alarm_flags & BessAlarm.COMM_LOSS

    def test_physics_keep_running_underneath(self) -> None:
        engine = make_engine()
        engine.setpoints.set_bess("bess1", BessSetpoint(1500, 0, BessMode.PQ))
        engine.apply_condition(CommLossChange(target=CommTarget.ASSET, id="bess1"))
        first = step(engine)
        later = step(engine, 10)
        assert later.bess[0].soc_pct == first.bess[0].soc_pct  # what is published is frozen
        assert later.poi.energy.wh_positive > first.poi.energy.wh_positive  # the site isn't

    def test_meters_go_stale_and_loads_flag(self) -> None:
        engine = make_engine(metered(site_config_dict()))
        for change in (
            CommLossChange(target=CommTarget.METER, id="m_bess1"),
            CommLossChange(target=CommTarget.POI_METER),
            CommLossChange(target=CommTarget.ASSET, id="load1"),
        ):
            engine.apply_condition(change)
        snapshot = step(engine)
        assert snapshot.meters[0].meter_state == MeterState.STALE
        assert snapshot.poi.meter_state == MeterState.STALE
        assert snapshot.loads[0].alarm_flags & LoadAlarm.COMM_LOSS
        assert snapshot.converged  # comm loss isn't a power flow failure

    def test_conditions_report_the_true_state(self) -> None:
        engine = make_engine()
        engine.apply_condition(CommLossChange(target=CommTarget.ASSET, id="bess1"))
        engine.apply_condition(BreakerChange(breaker="bess1", closed=False))
        snapshot = step(engine)
        assert snapshot.conditions is not None
        breakers = {item.id: item.closed for item in snapshot.conditions.breakers}
        assert breakers["bess1"] is False
        assert [item.id for item in snapshot.conditions.comm_loss] == ["bess1"]


class TestGridEvents:
    def test_voltage_sag_and_frequency(self) -> None:
        engine = make_engine()
        engine.apply_condition(GridVoltageChange(vm_pu=0.9))
        engine.apply_condition(GridFrequencyChange(hz=59.5))
        snapshot = step(engine)
        assert snapshot.poi.v_pu == pytest.approx(0.9, abs=0.02)
        assert 59.48 <= snapshot.poi.hz <= 59.52
        engine.apply_condition(GridVoltageChange(vm_pu=None))
        engine.apply_condition(GridFrequencyChange(hz=None))
        snapshot = step(engine)
        assert snapshot.poi.v_pu == pytest.approx(1.0, abs=0.02)
        assert 59.98 <= snapshot.poi.hz <= 60.02

    def test_frequency_alarm_bits(self) -> None:
        engine = make_engine()
        engine.apply_condition(GridFrequencyChange(hz=59.3))
        snapshot = step(engine)
        assert snapshot.bess[0].alarm_flags & BessAlarm.UNDER_FREQUENCY
        assert snapshot.pv[0].alarm_flags & PvAlarm.UNDER_FREQUENCY
        engine.apply_condition(GridFrequencyChange(hz=59.6))  # within nominal +- 0.5
        assert not step(engine).bess[0].alarm_flags & BessAlarm.UNDER_FREQUENCY
        engine.apply_condition(GridFrequencyChange(hz=60.7))
        assert step(engine).pv[0].alarm_flags & PvAlarm.OVER_FREQUENCY

    def test_disconnect_alarm_bits(self) -> None:
        engine = make_engine()
        engine.apply_condition(BreakerChange(breaker="bess1", closed=False))
        snapshot = step(engine)
        assert snapshot.bess[0].alarm_flags & BessAlarm.AC_DISCONNECT
        disconnected = PvAlarm.AC_DISCONNECT | PvAlarm.GRID_DISCONNECT
        assert not snapshot.pv[0].alarm_flags & disconnected
        engine.apply_condition(BreakerChange(breaker="poi", closed=False))
        snapshot = step(engine)
        assert snapshot.pv[0].alarm_flags & PvAlarm.GRID_DISCONNECT
        assert not snapshot.pv[0].alarm_flags & PvAlarm.UNDER_FREQUENCY  # 0 Hz: dead, no bit

    def test_clear_and_reset_return_to_the_config(self) -> None:
        engine = make_engine()
        engine.apply_condition(GridVoltageChange(vm_pu=0.9))
        engine.apply_condition(AssetFaultChange(asset_id="bess1"))
        cleared = engine.clear_conditions()
        assert cleared.grid_vm_pu is None and not cleared.faults
        engine.apply_condition(BreakerChange(breaker="poi", closed=False))
        asyncio.run(engine.reset())
        assert all(item.closed for item in engine.active_conditions().breakers)
