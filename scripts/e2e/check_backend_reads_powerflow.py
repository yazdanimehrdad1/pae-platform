"""E2E: backend-ot polls a seeded powerflow site and its readings agree with powerflow.

Checks a RUNNING dev stack through HTTP only: backend-ot's API for what it stored, powerflow's
device view (GET /api/devices: the same values its Modbus server serves) for what it should be.
No service code is imported; device naming and the site layout come from
contracts/powerflow/sites.json.

Live values move every simulation step, so the check pauses powerflow, waits for a backend-ot
poll taken after the pause, compares every seeded NATIVE point to powerflow's value as its
register holds it (rounded to the register's scale, saturated to its type), then resumes
powerflow. Unserved points aren't seeded; a value powerflow can't produce reads 0.

Usage (stdlib only; any Python 3.11+):
    uv run --no-project python scripts/e2e/check_backend_reads_powerflow.py \\
        [--api URL] [--powerflow-api URL] [--site 2bess_1pv] [--timeout S]
Run `make seed-2bess-1pv` first.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SITES_CONTRACT = REPO_ROOT / "contracts" / "powerflow" / "sites.json"
TYPE_RANGE = {
    "int16": (-(1 << 15), (1 << 15) - 1),
    "int32": (-(1 << 31), (1 << 31) - 1),
    "uint32": (0, (1 << 32) - 1),
    "bitfield32": (0, (1 << 32) - 1),
    "enum32": (0, (1 << 32) - 1),
}
DEFAULT_RANGE = (0, (1 << 16) - 1)  # uint16, enum16, bitfield16
# Mirrors backend-ot's seed naming (tests/seed_db/powerflow_seed.py: device_name).
NAME_BY_KIND = {"site": "plant_controller", "met_station": "met_station", "poi_meter": "poi_meter"}


def _request(url: str, method: str = "GET") -> Any:
    request = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read()
    return json.loads(body) if body else None


def _site_name(site: str) -> str:
    return "Powerflow " + " ".join(part.upper() for part in site.split("_"))


def _device_name(site: str, kind: str, asset_id: str) -> str:
    return f"{site}-{NAME_BY_KIND.get(kind, asset_id)}"


def _register_value(value: float | None, data_type: str, scale: float) -> float:
    """What backend-ot decodes from the register powerflow fills with `value`."""
    if value is None:
        return 0.0
    low, high = TYPE_RANGE.get(data_type, DEFAULT_RANGE)
    raw = min(max(round(value / scale), low), high)
    return raw * scale


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _check_once(api: str, powerflow_api: str, site: str, paused_at: datetime) -> tuple[bool, list[str]]:
    layout = json.loads(SITES_CONTRACT.read_text(encoding="utf-8"))["sites"][site]["devices"]
    expected_by_device = {
        _device_name(site, device["kind"], device["asset_id"]): device for device in layout
    }
    sites = _request(f"{api}/sites")
    site_id = next((item["site_id"] for item in sites if item["name"] == _site_name(site)), None)
    if site_id is None:
        return False, [f"site {_site_name(site)!r} not found — run make seed-{site.replace('_', '-')}"]
    backend_devices = {d["name"]: d for d in _request(f"{api}/devices/site/{site_id}/devices")}
    truth = {
        (device["kind"], device["asset_id"]): {point["point"]: point for point in device["points"]}
        for device in _request(f"{powerflow_api}/devices")["devices"]
    }

    complete = True
    lines = []
    for name, layout_device in expected_by_device.items():
        device = backend_devices.get(name)
        if device is None:
            complete = False
            lines.append(f"{name}: NOT SEEDED")
            continue
        points = _request(
            f"{api}/device-points/site/{site_id}/device/{device['device_id']}?category=NATIVE"
        )
        readings = _request(
            f"{api}/device-point-readings/site/{site_id}/device/{device['device_id']}/latest"
        )["readings"]
        reference = truth[(layout_device["kind"], layout_device["asset_id"])]
        fresh = 0
        mismatches = []
        for point in points:
            reading = readings.get(str(point["id"]))
            if reading is None or reading.get("time") is None or _parse_time(reading["time"]) <= paused_at:
                continue
            fresh += 1
            expected_point = reference[point["name"]]
            scale = point["scale_factor"] or 1.0
            expected = _register_value(expected_point["value"], point["data_type"], scale)
            actual = reading.get("value") or 0.0
            if abs(actual - expected) > max(abs(scale), 1e-9) * 1e-3 + 1e-6:
                mismatches.append(f"{point['name']}@{point['address']}={actual} expected {expected}")
        agrees = fresh == len(points) and not mismatches
        complete &= agrees
        lines.append(
            f"{name}: points={len(points)} fresh={fresh} mismatches={len(mismatches)}"
            + (f"  e.g. {mismatches[:3]}" if mismatches else "")
        )
    return complete, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000/api", help="backend-ot API base URL")
    parser.add_argument("--powerflow-api", default="http://localhost:8020/api", help="powerflow API base URL")
    parser.add_argument("--site", default="2bess_1pv", help="the seeded powerflow site")
    parser.add_argument("--timeout", type=float, default=90, help="seconds to wait for a fresh poll")
    args = parser.parse_args()

    try:
        status = _request(f"{args.powerflow_api}/sim/status")
        active = _request(f"{args.powerflow_api}/sites")["active"]
    except (urllib.error.URLError, ConnectionError) as error:
        print(f"powerflow API not reachable at {args.powerflow_api}: {error}")
        print("RESULT: DISAGREE")
        return 1
    if active != args.site:
        print(f"powerflow runs {active!r}, not {args.site!r}: run make seed-{args.site.replace('_', '-')}")
        print("RESULT: DISAGREE")
        return 1
    was_running = status["state"] == "running"
    # A just-(re)started simulation has no snapshot yet: let it take a step before pausing.
    for _ in range(30):
        if status["step_id"] > 0 or not was_running:
            break
        time.sleep(1)
        status = _request(f"{args.powerflow_api}/sim/status")
    if was_running:
        _request(f"{args.powerflow_api}/sim/pause", method="POST")
    paused_at = datetime.now(UTC)
    try:
        deadline = time.monotonic() + args.timeout
        while True:
            try:
                ok, lines = _check_once(args.api, args.powerflow_api, args.site, paused_at)
            except (urllib.error.URLError, ConnectionError) as error:
                ok, lines = False, [f"API not reachable: {error}"]
            if ok or time.monotonic() > deadline:
                break
            time.sleep(5)  # backend-ot polls every POLL_INTERVAL_SECONDS (default 10)
    finally:
        if was_running:
            _request(f"{args.powerflow_api}/sim/start", method="POST")

    print("\n".join(lines))
    print("RESULT:", "AGREE" if ok else "DISAGREE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
