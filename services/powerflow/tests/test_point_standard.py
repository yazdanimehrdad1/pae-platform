"""The point standard on top of the simulation: CSVs, register layout, encoding, resolvers."""

import asyncio
import math
from datetime import UTC, datetime, timedelta

import pytest
from conftest import POINT_STANDARD, PROFILES, default_site

from powerflow.conditions import (
    AssetFaultChange,
    BreakerChange,
    CommLossChange,
    CommTarget,
    GridFrequencyChange,
)
from powerflow.core.engine import Engine
from powerflow.core.point_registry import PointRegistry
from powerflow.core.runtime import SiteRuntime
from powerflow.core.setpoints import SetpointService
from powerflow.core.snapshot import Snapshot
from powerflow.models.bess import BessMode, BessSetpoint
from powerflow.models.grid import grid_frequency_hz
from powerflow.models.random_signal import PERIOD_MINUTE, PERIOD_SECOND, RandomSignal
from powerflow.models.status import LoadAlarm, LoadSupplyState
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.point_standard import (
    Device,
    DeviceKind,
    PointRow,
    ServerSupport,
    Sources,
    build_image,
    build_layout,
    encode,
    resolver_for,
)
from powerflow.point_standard.calc import CALC_RESOLVERS
from powerflow.point_standard.layout import POINT_LIST_FILE, device_template
from powerflow.point_standard.values import DIRECT_RESOLVERS
from powerflow.points import PointSource
from powerflow.site_config import SiteConfig


def kinds_using(file_name: str) -> list[DeviceKind]:
    if file_name == "common.csv":
        return list(DeviceKind)
    return [kind for kind, name in POINT_LIST_FILE.items() if name == file_name]


class TestCatalog:
    def test_every_csv_has_a_valid_powerflow_server_column(self) -> None:
        assert set(POINT_STANDARD.point_lists) >= set(POINT_LIST_FILE.values())
        for rows in POINT_STANDARD.point_lists.values():
            assert all(isinstance(row.support, ServerSupport) for row in rows)

    def test_strings_dropped_and_repeats_expanded(self) -> None:
        common = [row.point for row in POINT_STANDARD.rows("common.csv")]
        assert "Mn" not in common and "WMaxRtg" in common
        met = [row.point for row in POINT_STANDARD.rows("met_station.csv")]
        assert "POAI_1" in met and "POAI_<n>" not in met

    def test_enum_codes_come_from_the_standard(self) -> None:
        assert POINT_STANDARD.enums.code("802.ChaSt", "CHARGING") == 4
        assert POINT_STANDARD.enums.bits("701.Alrm", "AC_UNDER_VOLT") == 1 << 11


class TestResolversMatchTheColumn:
    """Drift test: the CSV's yes/calc says exactly which points have a resolver."""

    @pytest.mark.parametrize("file_name", sorted(POINT_STANDARD.point_lists))
    def test_every_yes_or_calc_point_has_a_resolver(self, file_name: str) -> None:
        for row in POINT_STANDARD.rows(file_name):
            if row.support is ServerSupport.NO:
                continue
            served = [kind for kind in kinds_using(file_name) if resolver_for(kind, row)]
            assert served, f"{file_name}: {row.point} is {row.support} but nothing serves it"

    @pytest.mark.parametrize(
        ("tables", "support"),
        [(DIRECT_RESOLVERS, ServerSupport.YES), (CALC_RESOLVERS, ServerSupport.CALC)],
    )
    def test_every_resolver_is_marked_in_its_csv(
        self, tables: dict[DeviceKind, dict[str, object]], support: ServerSupport
    ) -> None:
        for kind, resolvers in tables.items():
            rows = {
                row.point: row
                for row in (
                    *POINT_STANDARD.rows(POINT_LIST_FILE[kind]),
                    *POINT_STANDARD.rows("common.csv"),
                )
            }
            for point in resolvers:
                assert point in rows, f"{kind}: {point} isn't in the standard"
                assert rows[point].support is support, f"{kind}: {point} should be {support}"


class TestLayout:
    def test_reference_site_bases(self) -> None:
        devices = build_layout(default_site("2bess_1pv"), POINT_STANDARD)
        bases = {device.label: device.base for device in devices}
        assert bases == {
            "site.site": 0,
            "bess.bess1": 1000,
            "bess.bess2": 1100,
            "pv.pv1": 2000,
            "load.load1": 3000,
            "poi_meter.meter": 4000,
            "feeder_meter.m_bess1": 4100,
            "feeder_meter.m_bess2": 4200,
            "feeder_meter.m_pv1": 4300,
        }

    @pytest.mark.parametrize("site", ["2bess_1pv", "3bess_2pv", "1bess_1pv"])
    def test_chunks_fit_and_never_overlap(self, site: str) -> None:
        used: set[int] = set()
        for device in build_layout(default_site(site), POINT_STANDARD):
            for register in device.registers:
                addresses = set(range(register.address, register.address + register.row.width))
                assert not addresses & used, f"{device.label}.{register.row.point} overlaps"
                assert max(addresses) < device.base + 100
                used |= addresses

    def test_met_station_only_for_irradiance_pv(self) -> None:
        kinds = [device.kind for device in build_layout(default_site("1bess_1pv"), POINT_STANDARD)]
        assert DeviceKind.MET_STATION in kinds  # its PV is irradiance-driven
        reference = build_layout(default_site("2bess_1pv"), POINT_STANDARD)
        assert DeviceKind.MET_STATION not in [device.kind for device in reference]


def row(data_type: str, scale: float = 1.0) -> PointRow:
    return PointRow("X", data_type, scale, "", ServerSupport.YES)


class TestEncoding:
    def test_signed_16_bit_is_twos_complement(self) -> None:
        assert encode(-800_000, row("int16", 1000)) == [0xFFFF - 800 + 1]

    def test_scale_and_rounding(self) -> None:
        assert encode(478.14, row("uint16", 0.1)) == [4781]

    def test_32_bit_is_high_word_first(self) -> None:
        assert encode(0x0001_0002 * 1000, row("uint32", 1000)) == [0x0001, 0x0002]

    def test_values_saturate_to_the_type(self) -> None:
        assert encode(-5, row("uint16")) == [0]
        assert encode(1e12, row("int16")) == [0x7FFF]
        assert encode(math.nan, row("uint16")) == [0]


def reference_engine() -> tuple[Engine, PointRegistry]:
    config = default_site("2bess_1pv")
    simulation = config.simulation.model_copy(
        update={"test_mode": True, "start_time": datetime(2026, 1, 1, 12, tzinfo=UTC)}
    )
    config = config.model_copy(update={"simulation": simulation})
    engine = Engine(
        SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES
    )
    return engine, PointRegistry(engine, SetpointService(engine))


def sources_for(engine: Engine, registry: PointRegistry, snapshot: Snapshot) -> Sources:
    def read(name: str) -> float | int | bool:
        _, definition = registry.resolve(name)
        if definition.source is PointSource.MEASUREMENT:
            return registry.read_from_snapshot(snapshot, name)
        return registry.read(name)

    return Sources(snapshot, engine.config, read, POINT_STANDARD.enums)


def value(sources: Sources, devices: tuple[Device, ...], label: str, point: str) -> float:
    device = next(item for item in devices if item.label == label)
    register = next(item for item in device.registers if item.row.point == point)
    resolver = resolver_for(device.kind, register.row)
    assert resolver is not None, f"{label}.{point} isn't served"
    result = resolver(sources, device)
    assert result is not None
    return float(result)


class TestValues:
    def test_reference_site_values(self) -> None:
        engine, registry = reference_engine()
        engine.setpoints.set_bess("bess1", BessSetpoint(-400, 0, BessMode.PQ))
        snapshot = asyncio.run(engine.step(2))
        sources = sources_for(engine, registry, snapshot)
        devices = build_layout(engine.config, POINT_STANDARD)
        bess = snapshot.bess[0]

        assert value(sources, devices, "bess.bess1", "W") == pytest.approx(bess.p_kw * 1000)
        current = bess.s_kva / (math.sqrt(3) * bess.v_lv_kv)
        assert value(sources, devices, "bess.bess1", "AL2") == pytest.approx(current)
        assert value(sources, devices, "bess.bess1", "ChaSt") == 4  # CHARGING
        assert value(sources, devices, "bess.bess2", "ChaSt") == 6  # HOLDING (idle)
        assert value(sources, devices, "bess.bess1", "WSetEna") == 1
        assert value(sources, devices, "poi_meter.meter", "W") == pytest.approx(
            snapshot.poi.p_kw * 1000
        )
        assert value(sources, devices, "poi_meter.meter", "PhVphA") == pytest.approx(
            snapshot.poi.v_kv * 1000 / math.sqrt(3)
        )
        assert value(sources, devices, "feeder_meter.m_pv1", "W") == pytest.approx(
            snapshot.meters[2].p_kw * 1000
        )
        assert value(sources, devices, "site.site", "PvW") == pytest.approx(
            snapshot.pv[0].p_kw * 1000
        )
        assert value(sources, devices, "pv.pv1", "InvSt") in (3, 4)  # RUNNING or THROTTLED at noon

    def test_image_covers_served_points_only(self) -> None:
        engine, registry = reference_engine()
        snapshot = asyncio.run(engine.step(1))
        devices = build_layout(engine.config, POINT_STANDARD)
        image = build_image(devices, sources_for(engine, registry, snapshot))
        bess1 = next(device for device in devices if device.label == "bess.bess1")
        cabinet = next(register for register in bess1.registers if register.row.point == "TmpCab")
        assert cabinet.row.support is ServerSupport.NO and cabinet.address not in image
        soc = next(register for register in bess1.registers if register.row.point == "SoC")
        assert image[soc.address] == round(snapshot.bess[0].soc_pct / 0.1)


T0 = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


class TestRandomSignal:
    def test_holds_within_a_period_and_changes_across_periods(self) -> None:
        signal = RandomSignal(nominal=10.0, spread=1.0, period_s=PERIOD_MINUTE, key="test")
        first = signal.value_at(T0, seed=1)
        assert signal.value_at(T0 + timedelta(seconds=59), seed=1) == first
        later = [signal.value_at(T0 + timedelta(minutes=step), seed=1) for step in range(1, 6)]
        assert any(value != first for value in later)

    def test_deterministic_and_independent_streams(self) -> None:
        signal = RandomSignal(nominal=0.0, spread=1.0, period_s=PERIOD_SECOND, key="a")
        other_key = RandomSignal(nominal=0.0, spread=1.0, period_s=PERIOD_SECOND, key="b")
        assert signal.value_at(T0, seed=7) == signal.value_at(T0, seed=7)
        assert signal.value_at(T0, seed=7) != signal.value_at(T0, seed=8)
        assert signal.value_at(T0, seed=7) != other_key.value_at(T0, seed=7)

    def test_stays_within_nominal_plus_minus_spread(self) -> None:
        values = [
            grid_frequency_hz(T0 + timedelta(seconds=step), 3, None, energized=True)
            for step in range(500)
        ]
        assert all(59.98 <= value <= 60.02 for value in values)
        assert max(values) - min(values) > 0.02  # it really varies

    def test_custom_period(self) -> None:
        quarter_hour = RandomSignal(nominal=0.0, spread=1.0, period_s=900, key="q")
        assert quarter_hour.value_at(T0, seed=1) == quarter_hour.value_at(
            T0 + timedelta(minutes=14, seconds=59), seed=1
        )

    def test_rejects_a_bad_period(self) -> None:
        with pytest.raises(ValueError, match="period_s"):
            RandomSignal(nominal=0.0, spread=1.0, period_s=0, key="x")

    def test_every_device_reports_the_same_frequency(self) -> None:
        engine, registry = reference_engine()
        snapshot = asyncio.run(engine.step(1))
        sources = sources_for(engine, registry, snapshot)
        devices = build_layout(engine.config, POINT_STANDARD)
        readings = {
            value(sources, devices, "bess.bess1", "Hz"),
            value(sources, devices, "pv.pv1", "Hz"),
            value(sources, devices, "poi_meter.meter", "Hz"),
            value(sources, devices, "feeder_meter.m_bess1", "Hz"),
            value(sources, devices, "site.site", "SiteHz"),
        }
        assert len(readings) == 1 and 59.98 <= readings.pop() <= 60.02


def test_reference_site_enables_modbus() -> None:
    assert SiteConfig.model_validate(default_site("2bess_1pv")).interfaces.modbus.enabled


def test_load_codes_passed_through_match_the_standard() -> None:
    """values.py passes load supply_state / alarm_flags through raw ('yes'), which is only right
    while powerflow's codes equal the standard's pae.SupplySt / pae.LoadAlrm."""
    enums = POINT_STANDARD.enums
    for state in LoadSupplyState:
        assert enums.code("pae.SupplySt", state.name) == state.value
    for flag in LoadAlarm:
        if flag.value and flag.name:
            assert enums.bits("pae.LoadAlrm", flag.name) == flag.value


class TestInjectedConditions:
    """What the Modbus server shows for breakers, faults, comm loss and grid events."""

    def test_breaker_position_is_the_last_register_of_every_device(self) -> None:
        # Appended last, so adding it moved no existing address.
        for kind in DeviceKind:
            assert device_template(POINT_STANDARD, kind)[-1].row.point == "BrkPos"

    def test_breakers_faults_and_blackout(self) -> None:
        engine, registry = reference_engine()
        engine.apply_condition(BreakerChange(breaker="bess1", closed=False))
        engine.apply_condition(AssetFaultChange(asset_id="pv1"))
        sources = sources_for(engine, registry, asyncio.run(engine.step(1)))
        devices = build_layout(engine.config, POINT_STANDARD)
        enums = POINT_STANDARD.enums
        assert value(sources, devices, "bess.bess1", "BrkPos") == enums.code("pae.Dbpos", "OPEN")
        assert value(sources, devices, "bess.bess2", "BrkPos") == enums.code("pae.Dbpos", "CLOSED")
        assert value(sources, devices, "feeder_meter.m_bess1", "BrkPos") == enums.code(
            "pae.Dbpos", "OPEN"
        )
        assert value(sources, devices, "bess.bess1", "Hz") == 0  # de-energised
        assert value(sources, devices, "bess.bess1", "ConnSt") == enums.code(
            "701.ConnSt", "DISCONNECTED"
        )
        assert value(sources, devices, "pv.pv1", "InvSt") == enums.code("701.InvSt", "FAULT")
        assert value(sources, devices, "site.site", "NInvFlt") == 1
        assert value(sources, devices, "site.site", "GridMode") == enums.code(
            "pae.GridMode", "GRID_TIED"
        )
        engine.apply_condition(BreakerChange(breaker="poi", closed=False))
        sources = sources_for(engine, registry, asyncio.run(engine.step(1)))
        assert value(sources, devices, "site.site", "GridMode") == enums.code(
            "pae.GridMode", "BLACKOUT"
        )
        assert value(sources, devices, "site.site", "SiteHz") == 0

    def test_comm_loss_freezes_the_heartbeat_and_alarms_the_site(self) -> None:
        engine, registry = reference_engine()
        asyncio.run(engine.step(2))
        engine.apply_condition(CommLossChange(target=CommTarget.ASSET, id="bess1"))
        sources = sources_for(engine, registry, asyncio.run(engine.step(3)))
        devices = build_layout(engine.config, POINT_STANDARD)
        assert value(sources, devices, "bess.bess1", "Hb") == 2
        assert value(sources, devices, "bess.bess2", "Hb") == 5
        alarms = int(value(sources, devices, "site.site", "Alrm"))
        assert alarms & POINT_STANDARD.enums.bits("pae.PpcAlrm", "DEVICE_COMM_LOSS")

    def test_grid_frequency_excursion(self) -> None:
        engine, registry = reference_engine()
        engine.apply_condition(GridFrequencyChange(hz=59.5))
        sources = sources_for(engine, registry, asyncio.run(engine.step(1)))
        devices = build_layout(engine.config, POINT_STANDARD)
        assert 59.48 <= value(sources, devices, "pv.pv1", "Hz") <= 59.52
