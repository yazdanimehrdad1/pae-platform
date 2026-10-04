"""The Modbus adapter over a real TCP socket: reads, word order, holding = input, read-only."""

import asyncio

import pytest
from conftest import POINT_STANDARD, PROFILES, PROFILES_DIR, default_site
from fastapi.testclient import TestClient
from pymodbus.client import AsyncModbusTcpClient

from powerflow.app import create_app
from powerflow.core.engine import Engine
from powerflow.core.point_registry import PointRegistry
from powerflow.core.runtime import SiteRuntime
from powerflow.core.setpoints import SetpointService
from powerflow.core.site_library import SiteLibrary
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.modbus.adapter import ModbusAdapter
from powerflow.models.bess import BessMode, BessSetpoint
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.point_standard import build_layout
from powerflow.storage import InMemoryConfigRepository

UNIT_ID = 1


def make_adapter() -> tuple[ModbusAdapter, Engine]:
    config = default_site("2bess_1pv")
    simulation = config.simulation.model_copy(
        update={"test_mode": True, "start_time": config.simulation.start_time.replace(hour=12)}
    )
    config = config.model_copy(update={"simulation": simulation})
    engine = Engine(
        SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES
    )
    setpoints = SetpointService(engine)
    library = SiteLibrary(InMemoryConfigRepository(), PROFILES, engine, "2bess_1pv")
    context = AdapterContext(
        engine, PointRegistry(engine, setpoints), setpoints, library, POINT_STANDARD
    )
    return ModbusAdapter(context, "127.0.0.1", 0, UNIT_ID), engine


def address_of(engine: Engine, label: str, point: str) -> int:
    device = next(
        item for item in build_layout(engine.config, POINT_STANDARD) if item.label == label
    )
    return next(item.address for item in device.registers if item.row.point == point)


def signed16(raw: int) -> int:
    return raw - 0x10000 if raw >= 0x8000 else raw


def test_served_values_over_tcp() -> None:
    async def scenario() -> None:
        adapter, engine = make_adapter()
        await adapter.start()
        client = AsyncModbusTcpClient("127.0.0.1", port=adapter.port)
        try:
            engine.setpoints.set_bess("bess1", BessSetpoint(-500, 0, BessMode.PQ))
            await engine.step(10)  # counters are integrated by the simulation, every step
            adapter.refresh()
            snapshot = engine.store.latest
            assert snapshot is not None
            await client.connect()

            soc = address_of(engine, "bess.bess1", "SoC")
            response = await client.read_holding_registers(soc, count=1, device_id=UNIT_ID)
            assert response.registers == [round(snapshot.bess[0].soc_pct / 0.1)]

            poi_w = address_of(engine, "poi_meter.meter", "W")
            response = await client.read_input_registers(poi_w, count=1, device_id=UNIT_ID)
            assert signed16(response.registers[0]) == round(snapshot.poi.p_kw)  # scale 1000 W

            bess_w = address_of(engine, "bess.bess1", "W")
            response = await client.read_input_registers(bess_w, count=1, device_id=UNIT_ID)
            assert signed16(response.registers[0]) == round(snapshot.bess[0].p_kw) < 0  # charging

            # A 32-bit counter: high word first, and FC03 = FC04.
            counter = address_of(engine, "bess.bess1", "TotWhAbs")
            holding = await client.read_holding_registers(counter, count=2, device_id=UNIT_ID)
            inputs = await client.read_input_registers(counter, count=2, device_id=UNIT_ID)
            assert holding.registers == inputs.registers
            raw = (holding.registers[0] << 16) | holding.registers[1]
            # Every step counts (the simulation integrates the counters), the first one too.
            assert snapshot.bess[0].energy.wh_negative == pytest.approx(
                sum(-step.bess[0].p_kw * 1000 / 3600 for step in engine.store.history())
            )
            assert raw == round(snapshot.bess[0].energy.wh_negative / 1000) >= 1  # kWh resolution

            # Hz is the 60 Hz random signal (0.01 Hz units); unserved points read 0.
            hz = address_of(engine, "bess.bess1", "Hz")
            response = await client.read_input_registers(hz, count=1, device_id=UNIT_ID)
            assert 5998 <= response.registers[0] <= 6002
            cabinet = address_of(engine, "bess.bess1", "TmpCab")
            response = await client.read_input_registers(cabinet, count=1, device_id=UNIT_ID)
            assert response.registers == [0]
            site_w = address_of(engine, "site.site", "SiteW")
            response = await client.read_input_registers(site_w, count=1, device_id=UNIT_ID)
            assert signed16(response.registers[0]) == round(snapshot.poi.p_kw)
        finally:
            client.close()
            await adapter.stop()

    asyncio.run(scenario())


def test_writes_are_refused() -> None:
    async def scenario() -> None:
        adapter, engine = make_adapter()
        await adapter.start()
        client = AsyncModbusTcpClient("127.0.0.1", port=adapter.port)
        try:
            await client.connect()
            target = address_of(engine, "bess.bess1", "WSet")
            response = await client.write_register(target, 100, device_id=UNIT_ID)
            assert response.isError() and response.exception_code == 1  # ILLEGAL_FUNCTION
            assert engine.setpoints.bess("bess1").p_kw == 0
        finally:
            client.close()
            await adapter.stop()

    asyncio.run(scenario())


def test_layout_endpoint() -> None:
    repository = InMemoryConfigRepository.with_default_sites()
    with TestClient(create_app(PROFILES_DIR, repository)) as client:
        body = client.get("/api/modbus/registers").json()
    assert body["enabled"] is True and body["running"] is True and body["unit_id"] == UNIT_ID
    bases = {(device["kind"], device["asset_id"]): device["base"] for device in body["devices"]}
    assert bases[("bess", "bess1")] == 1000 and bases[("poi_meter", "meter")] == 4000
    bess1 = next(device for device in body["devices"] if device["asset_id"] == "bess1")
    soc = next(register for register in bess1["registers"] if register["point"] == "SoC")
    assert soc["powerflow_server"] == "yes" and soc["scale"] == 0.1
