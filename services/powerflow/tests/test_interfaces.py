"""Protocol interfaces follow the active site's config: started at startup, restarted on every
config change (activate, saving the active site), and a failed start is reported, not raised."""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.settings import settings
from powerflow.storage import InMemoryConfigRepository

# 2bess_1pv enables Modbus; 1bess_1pv doesn't.
WITH_MODBUS, WITHOUT_MODBUS = "2bess_1pv", "1bess_1pv"


@pytest.fixture
def client(profiles_copy: Path) -> Iterator[TestClient]:
    repository = InMemoryConfigRepository.with_default_sites()
    with TestClient(create_app(profiles_copy, repository)) as test_client:
        test_client.post("/api/sim/stop")
        yield test_client


def modbus_running(client: TestClient) -> bool:
    body = client.get("/api/modbus/registers").json()
    assert ("modbus" in client.get("/api/health").json()["interfaces"]) == body["running"]
    return body["running"]


def test_activate_starts_and_stops_modbus(client: TestClient) -> None:
    assert modbus_running(client)
    assert client.post(f"/api/sites/{WITHOUT_MODBUS}/activate").status_code == 200
    assert not modbus_running(client)
    assert client.post(f"/api/sites/{WITH_MODBUS}/activate").status_code == 200
    assert modbus_running(client)


def test_saving_the_active_site_applies_the_modbus_toggle(client: TestClient) -> None:
    site = client.get(f"/api/sites/{WITH_MODBUS}").json()
    site["interfaces"]["modbus"]["enabled"] = False
    assert client.put(f"/api/sites/{WITH_MODBUS}", json=site).status_code == 200
    assert not modbus_running(client)
    site["interfaces"]["modbus"]["enabled"] = True
    assert client.put(f"/api/sites/{WITH_MODBUS}", json=site).status_code == 200
    assert modbus_running(client)


def test_saving_another_site_leaves_the_interfaces_alone(client: TestClient) -> None:
    site = client.get(f"/api/sites/{WITHOUT_MODBUS}").json()
    site["interfaces"]["modbus"]["enabled"] = True
    assert client.put(f"/api/sites/{WITHOUT_MODBUS}", json=site).status_code == 200
    assert modbus_running(client)  # still the active site's server, unchanged


def test_a_port_in_use_is_reported_not_raised(
    profiles_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        monkeypatch.setattr(settings, "modbus_port", taken.getsockname()[1])
        repository = InMemoryConfigRepository.with_default_sites()
        with TestClient(create_app(profiles_copy, repository)) as client:
            health = client.get("/api/health").json()
            assert health["ok"] and health["interfaces"] == ["http"]
            assert "modbus" in health["interface_errors"]
            registers = client.get("/api/modbus/registers").json()
            assert registers["enabled"] and not registers["running"] and registers["error"]
