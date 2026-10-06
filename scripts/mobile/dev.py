"""Dev helper for trying services/mobile-plusdas on a phone against the running dev stack.

HTTP only (stdlib, no service code imported), like scripts/e2e/. The root Makefile wires it up:
    make mobile-dev     stack up + a site seeded if needed, prints what the phone needs, starts Metro

The site seeded when none exists is powerflow's 2bess_1pv ("Powerflow 2BESS 1PV" in backend-ot),
so the app has something to list.

Usage (any Python 3.11+):
    uv run --no-project python scripts/mobile/dev.py [--api URL] [--powerflow-api URL] \\
        {wait,has-demo-site,info}
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any

SITE_NAME = "Powerflow 2BESS 1PV"

FIREWALL_HINT = (
    "If the phone can't connect, allow the ports once (PowerShell as Administrator):\n"
    '    New-NetFirewallRule -DisplayName "PAE mobile dev" -Direction Inbound -Protocol TCP '
    "-LocalPort 8000,8081 -Action Allow -Profile Private\n"
    "and make sure Windows calls your Wi-Fi network 'Private' (Settings > Network > Wi-Fi)."
)


class DevError(Exception):
    """A problem with a message the developer can act on."""


def request(method: str, url: str, timeout: float = 10) -> Any:
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:300]
        raise DevError(f"{method} {url} -> {error.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        raise DevError(f"{method} {url} failed: {getattr(error, 'reason', error)}") from None
    return json.loads(raw) if raw else None


def reachable(url: str, timeout: float = 3) -> bool:
    try:
        request("GET", url, timeout=timeout)
        return True
    except DevError:
        return False


def lan_ip() -> str | None:
    """The address of the interface with the default route (no packet is sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
        except OSError:
            return None


def cmd_wait(args: argparse.Namespace) -> int:
    """Wait until backend-ot and powerflow both answer."""
    deadline = time.monotonic() + args.timeout
    targets = {"backend-ot": f"{args.api}/healthz", "powerflow": f"{args.powerflow_api}/health"}
    while True:
        missing = [name for name, url in targets.items() if not reachable(url)]
        if not missing:
            return 0
        if time.monotonic() >= deadline:
            print(f"not reachable: {', '.join(missing)}", file=sys.stderr)
            return 1
        time.sleep(2)


def cmd_has_demo_site(args: argparse.Namespace) -> int:
    return 0 if any(site["name"] == SITE_NAME for site in request("GET", f"{args.api}/sites")) else 1


def cmd_info(args: argparse.Namespace) -> int:
    ip = lan_ip()
    port = args.api.rsplit(":", 1)[-1].split("/")[0]
    print()
    print("=" * 72)
    if ip is None:
        print("Couldn't find this PC's LAN address: is it on Wi-Fi/Ethernet?")
    else:
        app_url = f"http://{ip}:{port}"
        on_lan = reachable(f"{app_url}/api/healthz")
        print(f"This PC on the LAN : {ip}")
        print(f"App will use       : {app_url}  (detected automatically, nothing to type)")
        print(f"backend-ot via LAN : {'OK' if on_lan else 'NOT reachable even from this PC'}")
        print(f"Phone check        : open {app_url}/api/healthz in the phone's browser")
    print()
    print("Next: scan the QR code below with Expo Go (Android) or the Camera app (iPhone).")
    print("      Phone and PC must be on the same Wi-Fi. The Sites tab lists backend-ot's sites.")
    if os.name == "nt":
        print()
        print(FIREWALL_HINT)
    print("=" * 72)
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000/api", help="backend-ot API base")
    parser.add_argument("--powerflow-api", default="http://localhost:8020/api", help="powerflow API base")
    commands = parser.add_subparsers(dest="command", required=True)
    wait = commands.add_parser("wait", help="wait for backend-ot and powerflow")
    wait.add_argument("--timeout", type=float, default=120)
    wait.set_defaults(run=cmd_wait)
    commands.add_parser("has-demo-site", help="exit 0 if powerflow's 2bess_1pv site is seeded").set_defaults(
        run=cmd_has_demo_site
    )
    commands.add_parser("info", help="print what the phone needs").set_defaults(run=cmd_info)
    args = parser.parse_args()
    args.api = args.api.rstrip("/")
    args.powerflow_api = args.powerflow_api.rstrip("/")
    try:
        return args.run(args)
    except DevError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
