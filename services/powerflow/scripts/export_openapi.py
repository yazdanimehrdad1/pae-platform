"""Write powerflow's contracts.

Usage: python scripts/export_openapi.py --output PATH [--points-output PATH]

Run via `make contract`, which passes the monorepo paths
(../../contracts/openapi/powerflow.openapi.json and ../../contracts/powerflow/points.json);
this script doesn't assume repo layout.
"""

import argparse
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from powerflow.app import create_app  # noqa: E402
from powerflow.contract import render_openapi_contract, render_points_contract  # noqa: E402


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
    args = parser.parse_args()
    write(args.output, render_openapi_contract(create_app()))
    if args.points_output is not None:
        write(args.points_output, render_points_contract())


if __name__ == "__main__":
    main()
