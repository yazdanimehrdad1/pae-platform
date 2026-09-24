"""Shared fixtures: a real mock-modbus server process on a free localhost port.

The server is started exactly as the container starts it (``python -m app.server``), so
the end-to-end tests exercise device discovery, settings, the datastore and the TCP
server together — no Docker needed. Every setting that affects reads is pinned in the
subprocess environment, so a developer's local ``.env`` can't change the results.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
STARTUP_TIMEOUT_S = 20.0
DEFAULT_REGISTER_VALUE = 7  # non-zero, so "unmapped" can't be confused with a real 0 reading


@dataclass(frozen=True)
class RunningServer:
    host: str
    port: int
    zero_mode: bool
    default_register_value: int


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _wait_until_listening(process: subprocess.Popen[bytes], port: int, log_path: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"mock-modbus exited with {process.returncode} during startup:\n"
                + log_path.read_text(encoding="utf-8", errors="replace")
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"mock-modbus did not listen on port {port} within {STARTUP_TIMEOUT_S}s")


@pytest.fixture(scope="session")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[RunningServer]:
    port = _free_port()
    environment = os.environ | {
        "AGGREGATOR_ENABLED": "true",
        "PER_DEVICE_ENABLED": "false",
        "MODBUS_HOST": "127.0.0.1",
        "MODBUS_PORT": str(port),
        "ZERO_MODE": "false",  # the default the dev stack runs with (backend-ot uses one_based)
        "RANDOM_SEED": "1234",
        "DEFAULT_REGISTER_VALUE": str(DEFAULT_REGISTER_VALUE),
        "LOG_LEVEL": "WARNING",  # INFO logs every read
        "PROFILE_TIMEZONE_OFFSET_HOURS": "0",
        "PROFILE_DAY_MINUTES": "1440",
    }
    log_path = tmp_path_factory.mktemp("mock-modbus") / "server.log"
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.server"],
            cwd=SERVICE_ROOT,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_until_listening(process, port, log_path)
            yield RunningServer(
                host="127.0.0.1",
                port=port,
                zero_mode=False,
                default_register_value=DEFAULT_REGISTER_VALUE,
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
