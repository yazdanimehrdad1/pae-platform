"""Write the register-map contract. Usage: python scripts/export_contract.py --output PATH

Run via `make contract`, which passes the monorepo path
(../../contracts/modbus/mock-modbus.devices.json); this script doesn't assume repo layout.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.contract import render_contract  # noqa: E402
from app.modbus_mock_data import DEVICES  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes on Windows and Linux, so the drift check is exact.
    with args.output.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(render_contract(DEVICES))
    print(f"wrote {args.output} ({len(DEVICES)} devices)")


if __name__ == "__main__":
    main()
