"""E2E: backend-ot is polling mock-modbus and its stored readings agree with the contract.

Checks a RUNNING stack (root dev stack, or the standalone pair) through backend-ot's HTTP
API only — no service code is imported, the expectations come from
contracts/modbus/mock-modbus.devices.json. Passes when every seeded point of every mock
device has a latest reading whose register value is inside the range mock-modbus
declares for that register.

Usage (stdlib only; any Python 3.11+):
    uv run --no-project python scripts/e2e/check_backend_reads_mock.py [--api URL] [--timeout S]
Run `make seed` (dev stack) or `make -C services/backend-ot seed-db` (standalone) first.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts" / "modbus" / "mock-modbus.devices.json"
SITE_NAME = "Alpha Solar Farm"


def _get(api: str, path: str) -> Any:
    with urllib.request.urlopen(f"{api}{path}", timeout=10) as response:
        return json.load(response)


def _seeded_name(mock_device_name: str) -> str:
    # Mirrors backend-ot's seed naming (tests/seed_db/mock_modbus_seed.py:seed_device_name).
    return f"mock-{mock_device_name.replace('_', '-')}"


def _check_once(api: str, contract: dict[str, Any]) -> tuple[bool, list[str]]:
    registers_by_device = {
        _seeded_name(device["name"]): {
            (register["file"], register["address"]): register for register in device["registers"]
        }
        for device in contract["devices"]
    }
    site_id = next((s["site_id"] for s in _get(api, "/sites") if s["name"] == SITE_NAME), None)
    if site_id is None:
        return False, [f"site {SITE_NAME!r} not found — seed the stack first"]
    devices = {d["name"]: d for d in _get(api, f"/devices/site/{site_id}/devices")}

    complete = True
    lines = []
    for name, registers in registers_by_device.items():
        device = devices.get(name)
        if device is None:
            complete = False
            lines.append(f"{name}: NOT SEEDED")
            continue
        points = _get(api, f"/device-points/site/{site_id}/device/{device['device_id']}")
        readings = _get(
            api, f"/device-point-readings/site/{site_id}/device/{device['device_id']}/latest"
        )["readings"]
        polled = 0
        out_of_range = []
        for point in points:
            reading = readings.get(str(point["id"]))
            if reading is None or reading.get("value") is None:
                continue
            polled += 1
            register = registers[(point["poll_kind"], point["address"])]
            # /latest returns the scaled engineering value; undo the scale for the register value.
            raw = round(reading["value"] / (point["scale_factor"] or 1.0))
            if not register["min"] <= raw <= register["max"]:
                out_of_range.append(
                    f"{point['name']}@{point['address']}={raw} not in [{register['min']}, {register['max']}]"
                )
        agrees = len(points) == len(registers) == polled and not out_of_range
        complete &= agrees
        lines.append(
            f"{name}: points={len(points)}/{len(registers)} polled={polled} "
            f"out_of_range={len(out_of_range)}" + (f"  e.g. {out_of_range[:3]}" if out_of_range else "")
        )
    return complete, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000/api", help="backend-ot API base URL")
    parser.add_argument("--timeout", type=float, default=90, help="seconds to wait for polling")
    args = parser.parse_args()

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    deadline = time.monotonic() + args.timeout
    while True:
        try:
            ok, lines = _check_once(args.api, contract)
        except (urllib.error.URLError, ConnectionError) as error:
            ok, lines = False, [f"backend-ot API not reachable at {args.api}: {error}"]
        if ok or time.monotonic() > deadline:
            break
        time.sleep(5)  # the scheduler polls every POLL_INTERVAL_SECONDS (default 10)

    print("\n".join(lines))
    print("RESULT:", "AGREE" if ok else "DISAGREE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
