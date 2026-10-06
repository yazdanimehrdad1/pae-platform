"""The app starts on a repository holding what a freshly migrated database holds: it loads the
default active site, starts its interfaces and autostarts the real-time loop. Nothing is
written to the repo."""

import time

from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.storage import InMemoryConfigRepository


def test_starts_and_runs_in_real_time() -> None:
    with TestClient(create_app(repository=InMemoryConfigRepository.with_default_sites())) as client:
        health = client.get("/api/health").json()
        assert health["ok"] and health["state"] == "running"
        assert health["interfaces"] == ["http", "modbus"]  # the default site enables Modbus
        deadline = time.monotonic() + 5
        while client.get("/api/sim/status").json()["step_id"] < 2 and time.monotonic() < deadline:
            time.sleep(0.2)
        status = client.get("/api/sim/status").json()
        assert status["step_id"] >= 2 and status["last_converged"] is True
