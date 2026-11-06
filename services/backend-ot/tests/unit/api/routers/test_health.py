"""
Unit tests for the device reachability probe behind /healthz/site/{site_id}[/device/{device_id}].

Guards that every device is probed twice (the aggregator and its own host/port), that the
top-level result is the probe of the path the poller reads through (read_from_aggregator picks
it), and that a failed connect is reported with its error and no latency.
"""

from datetime import UTC, datetime

import pytest

import api.routers.health as health
from config import settings
from schemas.api_models import DeviceListItem

DEVICE_HOST = "10.0.0.10"
DEVICE_PORT = 1502


def make_device(*, read_from_aggregator: bool) -> DeviceListItem:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return DeviceListItem(
        device_id=7,
        site_id=1001,
        name="bess-1",
        type="BESS",
        protocol="modbus_tcp",
        host=DEVICE_HOST,
        port=DEVICE_PORT,
        timeout=1.0,
        server_address=3,
        read_from_aggregator=read_from_aggregator,
        created_at=now,
        updated_at=now,
    )


class FakeModbusTcpClient:
    """Stands in for pymodbus: connects only to the host:port pairs in `reachable`."""

    reachable: set[tuple[str, int]] = set()
    raises: Exception | None = None

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.target = (host, port)

    def connect(self) -> bool:
        if self.raises is not None:
            raise self.raises
        return self.target in self.reachable

    def close(self) -> None:
        pass


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> type[FakeModbusTcpClient]:
    FakeModbusTcpClient.reachable = set()
    FakeModbusTcpClient.raises = None
    monkeypatch.setattr(health, "ModbusTcpClient", FakeModbusTcpClient)
    return FakeModbusTcpClient


AGGREGATOR = (settings.modbus_host, settings.modbus_port)


class TestBothTargetsAreProbed:
    async def test_aggregator_and_device_probes_target_their_own_host(self, fake_client) -> None:
        fake_client.reachable = {AGGREGATOR}

        status = await health._check_device_reachability(make_device(read_from_aggregator=True))

        assert (status.aggregator.host, status.aggregator.port) == AGGREGATOR
        assert status.aggregator.reachable is True
        assert status.aggregator.latency_ms is not None
        assert (status.device.host, status.device.port) == (DEVICE_HOST, DEVICE_PORT)
        assert status.device.reachable is False
        assert status.device.latency_ms is None
        assert status.device.error == "TCP connection refused or timed out"


class TestTopLevelIsThePolledPath:
    async def test_aggregator_device_reports_the_aggregator_probe(self, fake_client) -> None:
        fake_client.reachable = {AGGREGATOR}

        status = await health._check_device_reachability(make_device(read_from_aggregator=True))

        assert (status.host, status.port, status.reachable) == (*AGGREGATOR, True)
        assert status.error is None

    async def test_direct_device_reports_its_own_probe(self, fake_client) -> None:
        fake_client.reachable = {AGGREGATOR}

        status = await health._check_device_reachability(make_device(read_from_aggregator=False))

        assert (status.host, status.port, status.reachable) == (DEVICE_HOST, DEVICE_PORT, False)
        assert status.error == status.device.error


class TestConnectError:
    async def test_exception_is_reported_without_latency(self, fake_client) -> None:
        fake_client.raises = OSError("name resolution failed")

        status = await health._check_device_reachability(make_device(read_from_aggregator=False))

        for probe in (status.aggregator, status.device):
            assert probe.reachable is False
            assert probe.latency_ms is None
            assert probe.error == "name resolution failed"
