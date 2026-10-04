"""Point lists, point registry, setpoint service, adapter registry, Modbus map format."""

import asyncio

import pytest
from conftest import (
    POINT_STANDARD,
    PROFILES,
    default_site,
)
from pydantic import ValidationError

from powerflow.core.engine import Engine
from powerflow.core.point_registry import PointRegistry
from powerflow.core.runtime import SiteRuntime
from powerflow.core.setpoints import BessSetpointRequest, PvSetpointRequest, SetpointService
from powerflow.core.site_library import SiteLibrary
from powerflow.errors import (
    NoMeasurementError,
    PointAccessError,
    SetpointError,
    UnknownAssetError,
    UnknownPointError,
)
from powerflow.interfaces.base import AdapterContext, AdapterRegistry, ProtocolAdapter
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.points import POINT_LISTS, PointSource
from powerflow.site_config import SiteConfig
from powerflow.storage import InMemoryConfigRepository


def make_services(
    site_name: str = "3bess_2pv",
) -> tuple[Engine, SetpointService, PointRegistry]:
    config = default_site(site_name)
    config = config.model_copy(
        update={"simulation": config.simulation.model_copy(update={"test_mode": True})}
    )
    runtime = SiteRuntime.build(config, PROFILES, PandapowerSolver)
    engine = Engine(runtime, PandapowerSolver, PROFILES)
    service = SetpointService(engine)
    return engine, service, PointRegistry(engine, service)


def make_context(
    engine: Engine, service: SetpointService, registry: PointRegistry
) -> AdapterContext:
    library = SiteLibrary(InMemoryConfigRepository(), PROFILES, engine, "3bess_2pv")
    return AdapterContext(
        engine=engine,
        points=registry,
        setpoints=service,
        library=library,
        point_standard=POINT_STANDARD,
    )


class TestPointLists:
    def test_names_are_unique_per_asset_type(self) -> None:
        for definitions in POINT_LISTS.values():
            names = [definition.name for definition in definitions]
            assert len(names) == len(set(names))

    def test_every_point_maps_to_a_real_value(self) -> None:
        engine, _, registry = make_services()
        asyncio.run(engine.step(2))
        names = registry.names()
        assert len(names) > 100
        for name in names:
            value = registry.read(name)
            assert isinstance(value, int | float), name

    def test_measurement_points_available_in_history(self) -> None:
        engine, _, registry = make_services()
        asyncio.run(engine.step(1))
        snapshot = engine.store.history()[0]
        for name in registry.names(PointSource.MEASUREMENT):
            registry.read_from_snapshot(snapshot, name)
        with pytest.raises(PointAccessError):
            registry.read_from_snapshot(snapshot, "bess.bess1.p_setpoint_kw")

    def test_feeder_meter_points_resolve(self) -> None:
        engine, _, registry = make_services("2bess_1pv")
        asyncio.run(engine.step(1))
        meter_names = [name for name in registry.names() if name.startswith("meter.")]
        assert {name.split(".")[1] for name in meter_names} == {"m_bess1", "m_bess2", "m_pv1"}
        snapshot = engine.store.history()[0]
        for name in meter_names:
            assert registry.read(name) == registry.read_from_snapshot(snapshot, name)
        assert registry.read("meter.m_pv1.v_kv") == pytest.approx(12.47, rel=0.05)

    def test_measurement_before_first_step(self) -> None:
        _, _, registry = make_services()
        with pytest.raises(NoMeasurementError):
            registry.read("poi.meter.p_kw")
        assert registry.read("bess.bess1.capacity_kwh") == 10000  # nameplate needs no step

    @pytest.mark.parametrize(
        ("name", "error"),
        [
            ("bess.bess1", UnknownPointError),
            ("battery.bess1.p_kw", UnknownPointError),
            ("bess.bess9.p_kw", UnknownAssetError),
            ("bess.bess1.nope", UnknownPointError),
            ("poi.other.p_kw", UnknownAssetError),
        ],
    )
    def test_bad_names(self, name: str, error: type[Exception]) -> None:
        _, _, registry = make_services()
        with pytest.raises(error):
            registry.read(name)


class TestSetpointsViaRegistryMatchService:
    """A setpoint written through the registry (the path future Modbus/DNP3 use) is validated
    and clamped exactly like one written through the service (the path HTTP uses)."""

    @pytest.mark.parametrize(
        ("point", "field", "value"),
        [
            ("p_setpoint_kw", "p_kw", 4000.0),  # above the 2500 kW rating
            ("p_setpoint_kw", "p_kw", -1800.0),
            ("q_setpoint_kvar", "q_kvar", 3000.0),  # above S
        ],
    )
    def test_bess(self, point: str, field: str, value: float) -> None:
        _, service_a, _ = make_services()
        _, _, registry_b = make_services()
        via_service = service_a.write_bess(
            "bess1", BessSetpointRequest.model_validate({field: value})
        )
        via_registry = registry_b.write(f"bess.bess1.{point}", value)
        assert via_registry == via_service

    @pytest.mark.parametrize(
        ("point", "field", "value"),
        [
            ("p_limit_kw", "p_limit_kw", 9000.0),
            ("p_limit_pct", "p_limit_pct", 40.0),
            ("q_setpoint_kvar", "q_kvar", -5000.0),
            ("pf_setpoint", "pf", -0.9),
        ],
    )
    def test_pv(self, point: str, field: str, value: float) -> None:
        _, service_a, _ = make_services()
        _, _, registry_b = make_services()
        via_service = service_a.write_pv("pv1", PvSetpointRequest.model_validate({field: value}))
        via_registry = registry_b.write(f"pv.pv1.{point}", value)
        assert via_registry == via_service

    def test_clamping_is_reported(self) -> None:
        _, _, registry = make_services()
        result = registry.write("bess.bess1.p_setpoint_kw", 4000)
        assert result.clamped and result.flags == ["P_LIMIT"]
        assert registry.read("bess.bess1.p_setpoint_kw") == 2500

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("pv.pv1.pf_setpoint", 0.5),  # |pf| < 0.8
            ("pv.pv1.p_limit_pct", 150),
            ("pv.pv1.p_limit_kw", -1),
            ("bess.bess1.mode_cmd", 7),
            ("bess.bess1.p_setpoint_kw", float("nan")),
        ],
    )
    def test_invalid_values_are_rejected(self, name: str, value: float) -> None:
        _, _, registry = make_services()
        with pytest.raises(SetpointError):
            registry.write(name, value)

    def test_invalid_values_are_rejected_by_the_service_model_too(self) -> None:
        with pytest.raises(ValidationError):
            PvSetpointRequest(pf=0.5)
        with pytest.raises(ValidationError):
            PvSetpointRequest(p_limit_kw=100, p_limit_pct=10)

    def test_read_only_points_cant_be_written(self) -> None:
        _, _, registry = make_services()
        with pytest.raises(PointAccessError):
            registry.write("bess.bess1.soc_pct", 50)

    def test_written_setpoints_drive_the_next_step(self) -> None:
        engine, _, registry = make_services()
        registry.write("bess.bess1.mode_cmd", 1)  # pq
        registry.write("bess.bess1.p_setpoint_kw", 400)  # within the 500 kW/s ramp
        registry.write("pv.pv1.p_limit_kw", 0)
        asyncio.run(engine.step(1))
        assert registry.read("bess.bess1.p_kw") == pytest.approx(400)
        assert registry.read("pv.pv1.p_kw") == 0
        assert registry.read("bess.bess1.mode_cmd") == 1


class RecordingAdapter(ProtocolAdapter):
    name = "modbus"

    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def start(self) -> None:
        self.events.append("start")

    async def stop(self) -> None:
        self.events.append("stop")


class TestAdapterRegistry:
    def test_enabled_but_unimplemented_is_skipped(self) -> None:
        engine, service, registry = make_services()
        config = SiteConfig.model_validate({"interfaces": {"dnp3": {"enabled": True}}})
        adapters = AdapterRegistry()
        asyncio.run(adapters.reconcile(config.interfaces, make_context(engine, service, registry)))
        assert adapters.running == [] and adapters.failed == {}

    def test_enabled_adapter_starts_and_stops(self) -> None:
        engine, service, registry = make_services()
        events: list[str] = []
        adapters = AdapterRegistry()
        adapters.register("modbus", lambda context: RecordingAdapter(events))
        context = make_context(engine, service, registry)
        disabled = SiteConfig.model_validate({})
        asyncio.run(adapters.reconcile(disabled.interfaces, context))
        assert events == []
        enabled = SiteConfig.model_validate({"interfaces": {"modbus": {"enabled": True}}})
        asyncio.run(adapters.reconcile(enabled.interfaces, context))
        assert adapters.running == ["modbus"]
        asyncio.run(adapters.reconcile(enabled.interfaces, context))  # restarted
        asyncio.run(adapters.reconcile(disabled.interfaces, context))  # stopped
        assert events == ["start", "stop", "start", "stop"] and adapters.running == []

    def test_a_failed_start_is_reported_not_raised(self) -> None:
        engine, service, registry = make_services()

        class PortTaken(RecordingAdapter):
            async def start(self) -> None:
                raise OSError("address already in use")

        adapters = AdapterRegistry()
        adapters.register("modbus", lambda context: PortTaken([]))
        enabled = SiteConfig.model_validate({"interfaces": {"modbus": {"enabled": True}}})
        asyncio.run(adapters.reconcile(enabled.interfaces, make_context(engine, service, registry)))
        assert adapters.running == []
        assert "address already in use" in adapters.failed["modbus"]

    def test_http_cant_be_disabled(self) -> None:
        with pytest.raises(ValidationError):
            SiteConfig.model_validate({"interfaces": {"http": {"enabled": False}}})
