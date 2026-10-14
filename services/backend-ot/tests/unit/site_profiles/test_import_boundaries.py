"""
Guards the dependency direction between site_profiles and the rest of the service.

helpers.alarms imports site_profiles (profile_sync reads the declared alarms, evaluation runs
them), and api / scheduler sit on top of everything. If site_profiles imported any of them the
packages would depend on each other, and one innocent import could make the app fail to start
with a circular import. site_profiles reads what it needs from the database itself (see
site_profiles/common/shared_helper_functions.py). Imports inside functions count too.
"""

import ast
from pathlib import Path

import pytest

import site_profiles

SITE_PROFILES_DIR = Path(site_profiles.__file__).parent
FORBIDDEN_PREFIXES = ("helpers.alarms", "api", "scheduler")


def imported_modules(path: Path) -> list[str]:
    """Every absolute module name the file imports, wherever the import statement is."""
    modules: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
    return modules


def is_forbidden(module: str) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_PREFIXES)


SITE_PROFILE_FILES = sorted(SITE_PROFILES_DIR.rglob("*.py"))


@pytest.mark.parametrize(
    "path", SITE_PROFILE_FILES, ids=lambda path: path.relative_to(SITE_PROFILES_DIR).as_posix()
)
def test_site_profiles_does_not_import_alarms_api_or_scheduler(path: Path):
    forbidden = [module for module in imported_modules(path) if is_forbidden(module)]
    assert forbidden == [], (
        f"{path.name} imports {forbidden}; read the database directly instead"
    )


def test_the_scan_sees_the_package():
    # guards the guard: an empty file list would make every check above pass vacuously
    assert any(path.name == "shared_health.py" for path in SITE_PROFILE_FILES)


@pytest.mark.parametrize(
    ("module", "forbidden"),
    [
        ("helpers.alarms.events", True),
        ("helpers.alarms", True),
        ("api.routers.alarms", True),
        ("scheduler.jobs", True),
        ("helpers.reads.device_points_readings", False),
        ("apis_client", False),  # a prefix match needs the dot
    ],
)
def test_forbidden_prefix_matching(module: str, forbidden: bool):
    assert is_forbidden(module) is forbidden
