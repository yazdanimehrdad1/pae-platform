"""Scaffold services/<name>/ from templates/<kind>/. Stdlib only.

Usage (from the repo root):
    uv run --no-project python .claude/skills/new-service/scaffold.py \
        --name optimizer --port 8010 --description "Dispatch optimizer for site assets"
    uv run --no-project python .claude/skills/new-service/scaffold.py --kind node \
        --name ops-console --port 5175 --description "Operator console for dispatch"

--kind python (default): FastAPI app that publishes an OpenAPI contract.
--kind node: Vite + React SPA served by nginx, /api proxied same-origin to backend-ot, API types
generated from backend-ot's contract (the layout of services/web-plusdas).

Writes files only; registration in the root Makefile, dev stack, port registry and CLAUDE.md
is done by hand (see SKILL.md). Refuses to overwrite an existing service directory.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
TEMPLATES_ROOT = SKILL_DIR / "templates"
KINDS = ("python", "node")
REPO_ROOT = SKILL_DIR.parents[2]
SERVICE_NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def placeholders(name: str, port: int, description: str) -> dict[str, str]:
    return {
        "__SERVICE__": name,
        "__PACKAGE__": name.replace("-", "_"),
        "__ENV_PREFIX__": name.replace("-", "_").upper(),
        "__PORT__": str(port),
        # Node only: the Vite dev server (`make run`) takes the next port, like web-plusdas.
        "__DEV_PORT__": str(port + 1),
        "__DESCRIPTION__": description,
    }


def render(text: str, values: dict[str, str]) -> str:
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="kebab-case service directory name")
    parser.add_argument("--port", required=True, type=int, help="host HTTP port from the registry")
    parser.add_argument("--description", required=True, help="one line: what the service does")
    parser.add_argument("--kind", choices=KINDS, default="python", help="template set (default: python)")
    args = parser.parse_args()

    if not SERVICE_NAME.match(args.name):
        parser.error("--name must be lowercase kebab-case starting with a letter (compose project rule)")
    if '"' in args.description or "\n" in args.description:
        parser.error("--description must be one line without double quotes")
    service_dir = REPO_ROOT / "services" / args.name
    if service_dir.exists():
        parser.error(f"{service_dir.relative_to(REPO_ROOT).as_posix()} already exists")

    values = placeholders(args.name, args.port, args.description)
    written: list[Path] = []
    templates_dir = TEMPLATES_ROOT / args.kind
    for template in sorted(templates_dir.rglob("*.tmpl")):
        relative = Path(render(template.relative_to(templates_dir).as_posix(), values))
        target = service_dir / relative.with_suffix("")  # drop .tmpl
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as output_file:
            output_file.write(render(template.read_text(encoding="utf-8"), values))
        written.append(target)

    for path in written:
        print(f"wrote {path.relative_to(REPO_ROOT).as_posix()}")
    print(f"next: follow the registration steps in {SKILL_DIR.relative_to(REPO_ROOT).as_posix()}/SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
