"""Enforce the monorepo's service boundaries. Stdlib only. Usage: python scripts/check_boundaries.py

Services live in services/<name>/ and share nothing but contracts/. This fails (exit 1) when:

1. Cross-service import: a Python file in service A imports a module that does not resolve
   inside A but does resolve inside another service B. Import roots per service are the
   service directory, its src/ and its tests/ (the layouts in use: flat `src/` modules,
   `app/` packages, tests importing `unit.`/`integration.`).
2. Cross-service path: a `../` path in a service's code or config resolves into another
   service's directory.
3. Escaping build/config path: a compose file, Dockerfile or pyproject.toml uses a `../` path
   that leaves its own service, other than into contracts/.
4. Dev-only leak: mock-modbus (DEV-ONLY) is named in a production manifest — anything under a
   service's k8s/ or .github/, or under deploy/ outside deploy/compose/ (the dev stack).

Mentioning another service by name (e.g. "run `make -C services/mock-modbus contract`") is fine;
reading or importing its files is not. Judgement calls are left to the boundary-reviewer agent.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = REPO_ROOT / "services"
CONTRACTS_DIR = REPO_ROOT / "contracts"
DEV_STACK_DIR = REPO_ROOT / "deploy" / "compose"
DEV_ONLY_SERVICE = re.compile(r"mock[-_]modbus", re.IGNORECASE)

SKIPPED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", ".ruff_cache", ".pytest_cache",
    ".mypy_cache", "build", "dist",
}
# Files whose `../` paths are checked. Build/config files may only leave the service for
# contracts/; the rest may not reach into another service.
BUILD_CONFIG_PATTERNS = ("compose*.yaml", "compose*.yml", "Dockerfile*", "pyproject.toml")
CODE_PATTERNS = ("*.py", "Makefile", "*.sh", "*.yaml", "*.yml", "*.toml", "Dockerfile*")
RELATIVE_PATH = re.compile(r"(?:\.\./)+[\w.\-/]*")


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path.relative_to(REPO_ROOT).as_posix()}:{self.line}: {self.message}"


def service_dirs() -> list[Path]:
    return sorted(
        path for path in SERVICES_DIR.iterdir() if path.is_dir() and not path.name.startswith(".")
    )


def iter_files(service_dir: Path, patterns: tuple[str, ...]) -> list[Path]:
    found: set[Path] = set()
    for pattern in patterns:
        for path in service_dir.rglob(pattern):
            relative_parts = path.relative_to(service_dir).parts
            if path.is_file() and not SKIPPED_DIRS.intersection(relative_parts):
                found.add(path)
    return sorted(found)


def import_roots(service_dir: Path) -> list[Path]:
    return [root for root in (service_dir, service_dir / "src", service_dir / "tests") if root.is_dir()]


def resolves_in(module: str, roots: list[Path]) -> bool:
    relative = Path(*module.split("."))
    for root in roots:
        candidate = root / relative
        if candidate.with_suffix(".py").is_file() or candidate.is_dir():
            return True
    return False


def imported_modules(tree: ast.AST) -> list[tuple[int, list[str]]]:
    """(line, candidate module names) per absolute import; any candidate resolving counts."""
    imports: list[tuple[int, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, [alias.name]) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            candidates = [f"{node.module}.{alias.name}" for alias in node.names] + [node.module]
            imports.append((node.lineno, candidates))
    return imports


def check_imports(service_dir: Path, others: list[Path]) -> list[Violation]:
    own_roots = import_roots(service_dir)
    other_roots = {other.name: import_roots(other) for other in others}
    stdlib = sys.stdlib_module_names
    violations: list[Violation] = []
    for path in iter_files(service_dir, ("*.py",)):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as error:
            violations.append(Violation(path, 1, f"cannot parse: {error}"))
            continue
        for line, candidates in imported_modules(tree):
            if candidates[-1].split(".")[0] in stdlib:
                continue
            if any(resolves_in(candidate, own_roots) for candidate in candidates):
                continue
            for other_name, roots in other_roots.items():
                if any(resolves_in(candidate, roots) for candidate in candidates):
                    violations.append(Violation(
                        path, line, f"imports `{candidates[-1]}` from service {other_name}"
                    ))
    return violations


def owning_service(target: Path, services: list[Path]) -> Path | None:
    for service in services:
        if target == service or service in target.parents:
            return service
    return None


def check_paths(service_dir: Path, services: list[Path]) -> list[Violation]:
    violations: list[Violation] = []
    build_config = set(iter_files(service_dir, BUILD_CONFIG_PATTERNS))
    for path in iter_files(service_dir, CODE_PATTERNS):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number, line in enumerate(lines, start=1):
            for match in RELATIVE_PATH.finditer(line):
                relative = match.group(0)
                # The base depends on the tool: the file's directory (compose, imports) or the
                # service root (Dockerfile build context, Makefile recipes). Try both.
                targets = [(base / relative).resolve() for base in (path.parent, service_dir)]
                owners = [owning_service(target, services) for target in targets]
                other_owner = next(
                    (owner for owner in owners if owner is not None and owner != service_dir), None
                )
                if other_owner is not None:
                    violations.append(Violation(
                        path, line_number, f"path `{relative}` reaches into service {other_owner.name}"
                    ))
                elif path in build_config and all(
                    owner is None and not (target == CONTRACTS_DIR or CONTRACTS_DIR in target.parents)
                    for target, owner in zip(targets, owners, strict=True)
                ):
                    violations.append(Violation(
                        path, line_number, f"path `{relative}` leaves the service (only contracts/ is shared)"
                    ))
    return violations


def production_files() -> list[Path]:
    roots = [REPO_ROOT / "deploy"] + [
        service / name for service in service_dirs() for name in ("k8s", ".github")
    ]
    files = [path for root in roots if root.is_dir() for path in root.rglob("*") if path.is_file()]
    return sorted(
        path for path in files if not (path == DEV_STACK_DIR or DEV_STACK_DIR in path.parents)
    )


def check_dev_only_leaks() -> list[Violation]:
    violations: list[Violation] = []
    for path in production_files():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        violations.extend(
            Violation(path, line_number, "names the DEV-ONLY mock-modbus in a production manifest")
            for line_number, line in enumerate(lines, start=1)
            if DEV_ONLY_SERVICE.search(line)
        )
    return violations


def main() -> int:
    services = service_dirs()
    violations: list[Violation] = []
    for service_dir in services:
        others = [other for other in services if other != service_dir]
        violations += check_imports(service_dir, others)
        violations += check_paths(service_dir, services)
    violations += check_dev_only_leaks()
    for violation in violations:
        print(violation, file=sys.stderr)
    if violations:
        print(f"check-boundaries: {len(violations)} violation(s)", file=sys.stderr)
        return 1
    print(f"check-boundaries: {len(services)} services, no violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
