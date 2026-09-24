"""Write backend-ot's OpenAPI contract. Usage: python scripts/export_openapi.py --output PATH

Run via `make contract`, which passes the monorepo path
(../../contracts/openapi/backend-ot.openapi.json); this script doesn't assume repo layout.
Building the app opens no connections (postgres/redis/scheduler start in the lifespan, which
never runs here), but config.py requires POSTGRES_PASSWORD, so the Makefile passes a dummy.
"""

import argparse
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from app import app  # noqa: E402
from contract import render_openapi_contract  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes on Windows and Linux, so the drift check is exact.
    with args.output.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(render_openapi_contract(app))
    print(f"wrote {args.output} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()
