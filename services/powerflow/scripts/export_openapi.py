"""Write powerflow's contracts.

Usage: python scripts/export_openapi.py --output PATH [--points-output PATH]
                                         [--registers-output PATH]

Run via `make contract`, which passes the monorepo paths
(../../contracts/openapi/powerflow.openapi.json, ../../contracts/powerflow/points.json and
../../contracts/modbus/powerflow.registers.json); this script doesn't assume repo layout.
"""

import argparse
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from powerflow.app import create_app  # noqa: E402
from powerflow.contract import (  # noqa: E402
    render_openapi_contract,
    render_points_contract,
    render_registers_contract,
)
from powerflow.point_standard import load_point_standard  # noqa: E402
from powerflow.settings import settings  # noqa: E402
from powerflow.storage.defaults import read_defaults  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes on Windows and Linux, so the drift check is exact.
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(text)
    print(f"wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--points-output", type=Path)
    parser.add_argument("--registers-output", type=Path)
    args = parser.parse_args()
    write(args.output, render_openapi_contract(create_app()))
    if args.points_output is not None:
        write(args.points_output, render_points_contract())
    if args.registers_output is not None:
        standard = load_point_standard(settings.resolved_point_standard_dir())
        defaults = read_defaults(settings.resolved_site_config_dir())
        sites = {site.name: site.config for site in defaults.sites}
        write(args.registers_output, render_registers_contract(standard, sites))


if __name__ == "__main__":
    main()
