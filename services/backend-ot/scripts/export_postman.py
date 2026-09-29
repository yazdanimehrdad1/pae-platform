"""Write backend-ot's Postman collection. Usage: python scripts/export_postman.py --output PATH

Run via `make postman`. Like `make contract`, it builds the app to read its OpenAPI spec (no
connections are opened), so the Makefile passes the same dummy POSTGRES_PASSWORD.
"""

import argparse
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from app import app  # noqa: E402
from postman_collection import render_postman_collection  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes on Windows and Linux.
    with args.output.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(render_postman_collection(app))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
