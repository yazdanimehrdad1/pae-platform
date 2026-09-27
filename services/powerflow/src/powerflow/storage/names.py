"""Name rules for stored sites, Modbus maps and profile scenarios."""

import re

from powerflow.errors import InvalidNameError
from powerflow.site_config.models import SCENARIO_PATTERN

SITE_NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")
MAP_NAME_PATTERN = re.compile(r"^(bess|pv|load|poi|site)\.[A-Za-z0-9_-]+$")
SCENARIO_NAME_PATTERN = re.compile(SCENARIO_PATTERN)
# Device names Windows won't use as file names (profiles are files; `make run` on Windows).
WINDOWS_RESERVED_NAMES = {"con", "prn", "aux", "nul"} | {
    f"{port}{number}" for port in ("com", "lpt") for number in range(1, 10)
}


def check_name(name: str, pattern: re.Pattern[str], kind: str) -> str:
    if not pattern.fullmatch(name) or name.split(".")[0].lower() in WINDOWS_RESERVED_NAMES:
        raise InvalidNameError(f"invalid {kind} name {name!r} (allowed: {pattern.pattern})")
    return name


def check_site_name(name: str) -> str:
    return check_name(name, SITE_NAME_PATTERN, "site")


def check_map_name(name: str) -> str:
    return check_name(name, MAP_NAME_PATTERN, "Modbus map")
