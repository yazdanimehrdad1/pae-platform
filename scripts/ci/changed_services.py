"""Which services CI must check, and which production images it must build. Stdlib only.

Usage (GitHub Actions writes the result to $GITHUB_OUTPUT):
    python scripts/ci/changed_services.py --all
    python scripts/ci/changed_services.py --base <sha> --head <sha>

A service is selected when a file under services/<name>/ changed, when a contract it provides or
consumes changed (the consumers are the ones listed in contracts/README.md; keep CONTRACT_USERS in
step with it), or when shared CI/tooling changed (then every service). `--all` (push to main,
manual runs) selects everything.

Prints two JSON lists:
- services: [{"service", "toolchain" (python|node), "integration" (bool)}] for the per-service checks;
- images: [{"service", "context", "dockerfile"}] for the production images among the selected
  services. Only the four deployed services have one; mock-modbus (DEV-ONLY) and mobile-plusdas
  (not containerized) never do.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Service:
    service: str
    toolchain: str
    integration: bool


@dataclass(frozen=True)
class Image:
    service: str
    context: str
    dockerfile: str


SERVICES = (
    Service("backend-ot", "python", integration=True),
    Service("mock-modbus", "python", integration=False),
    Service("web-plusdas", "node", integration=False),  # its test-integration needs the dev stack
    Service("powerflow", "python", integration=True),
    Service("mobile-plusdas", "node", integration=False),
    Service("intelli-gateway", "python", integration=True),
)

# The production images: one per deployed service, built from the service's own directory.
IMAGES = (
    Image("backend-ot", "services/backend-ot", "services/backend-ot/docker/Dockerfile"),
    Image("intelli-gateway", "services/intelli-gateway", "services/intelli-gateway/Dockerfile"),
    Image("powerflow", "services/powerflow", "services/powerflow/Dockerfile"),
    Image("web-plusdas", "services/web-plusdas", "services/web-plusdas/docker/Dockerfile"),
)

# contracts/<path> -> the provider and its consumers (contracts/README.md).
CONTRACT_USERS: dict[str, tuple[str, ...]] = {
    "openapi/backend-ot.openapi.json": ("backend-ot", "web-plusdas", "mobile-plusdas", "intelli-gateway"),
    "openapi/powerflow.openapi.json": ("powerflow", "web-plusdas"),
    "openapi/intelli-gateway.openapi.json": ("intelli-gateway", "web-plusdas"),
    "modbus/mock-modbus.devices.json": ("mock-modbus", "backend-ot"),
    "modbus/powerflow.registers.json": ("powerflow", "backend-ot"),
    "powerflow/sites.json": ("powerflow", "backend-ot"),
    "powerflow/points.json": ("powerflow",),
}

# A change here can break any service's CI run, so every service is checked.
SHARED_PREFIXES = (".github/workflows/", "scripts/ci/", "Makefile")


def select_services(changed_paths: list[str]) -> list[str]:
    known = {service.service for service in SERVICES}
    selected: set[str] = set()
    for path in changed_paths:
        if path.startswith(SHARED_PREFIXES):
            return [service.service for service in SERVICES]
        parts = path.split("/")
        if parts[0] == "services" and len(parts) > 2 and parts[1] in known:
            selected.add(parts[1])
        elif parts[0] == "contracts" and path.endswith(".json"):
            users = CONTRACT_USERS.get("/".join(parts[1:]))
            if users is None:
                # A contract this script doesn't know yet: check everything rather than nothing.
                return [service.service for service in SERVICES]
            selected.update(users)
    return [service.service for service in SERVICES if service.service in selected]


def build_outputs(selected: list[str]) -> dict[str, str]:
    services = [asdict(service) for service in SERVICES if service.service in selected]
    images = [asdict(image) for image in IMAGES if image.service in selected]
    return {"services": json.dumps(services), "images": json.dumps(images)}


def changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="select every service")
    parser.add_argument("--base", help="base commit of the change")
    parser.add_argument("--head", default="HEAD", help="head commit of the change")
    args = parser.parse_args()
    if args.all:
        selected = [service.service for service in SERVICES]
    elif args.base:
        selected = select_services(changed_files(args.base, args.head))
    else:
        parser.error("pass --all or --base")
    outputs = build_outputs(selected)
    for name, value in outputs.items():
        print(f"{name}={value}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            for name, value in outputs.items():
                handle.write(f"{name}={value}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
