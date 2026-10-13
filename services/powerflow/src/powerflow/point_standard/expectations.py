"""An event scenario's expected points, against the point standard: are they valid for a site's
device layout (a served point on an existing device, symbols the point knows), and does a step's
snapshot meet them. Values are the engineering values (the same as /api/devices)."""

import math
from collections.abc import Callable, Sequence

from powerflow.conditions.scenario import EventScenario, ExpectedPoint
from powerflow.errors import PointStandardError
from powerflow.point_standard.catalog import PointRow, PointStandard, ServerSupport
from powerflow.point_standard.layout import Device, build_layout
from powerflow.point_standard.readings import resolve_point
from powerflow.point_standard.sources import Sources
from powerflow.site_config import SiteConfig


def _symbol_code(row: PointRow, symbol: str) -> int | None:
    for code, label in (row.enum_detail or {}).items():
        if label == symbol:
            return int(code)
    return None


def _bit(row: PointRow, symbol: str) -> int | None:
    for bit, label in (row.bitfield_detail or {}).items():
        if label == symbol:
            return int(bit)
    return None


def _find(devices: Sequence[Device], expected: ExpectedPoint) -> tuple[Device, PointRow] | str:
    device = next((item for item in devices if item.label == expected.device), None)
    if device is None:
        return f"no device {expected.device!r}"
    row = next((item.row for item in device.registers if item.row.point == expected.point), None)
    if row is None:
        return f"{expected.device} has no point {expected.point!r}"
    return device, row


def point_problems(expected: ExpectedPoint, devices: Sequence[Device]) -> list[str]:
    """Why this expectation can't be checked on this layout (empty = fine)."""
    found = _find(devices, expected)
    if isinstance(found, str):
        return [found]
    _, row = found
    name = f"{expected.device}.{expected.point}"
    problems: list[str] = []
    if row.support is ServerSupport.NO:
        problems.append(f"{name} isn't simulated (it always reads 0)")
    if isinstance(expected.equals, str) and _symbol_code(row, expected.equals) is None:
        problems.append(f"{name} has no value {expected.equals!r}")
    for symbol in [*expected.bits_set, *expected.bits_clear]:
        if _bit(row, symbol) is None:
            problems.append(f"{name} has no bit {symbol!r}")
    return problems


def expectation_problems(scenario: EventScenario, devices: Sequence[Device]) -> list[str]:
    return [
        f"expected point {index}: {problem}"
        for index, expected in enumerate(scenario.expected_points, start=1)
        for problem in point_problems(expected, devices)
    ]


def expected_point_check(
    standard: PointStandard,
) -> Callable[[EventScenario, SiteConfig], list[str]]:
    """The EventScenarioLibrary's check: the expected points against the site's layout."""

    def check_points(scenario: EventScenario, config: SiteConfig) -> list[str]:
        if not scenario.expected_points:
            return []
        try:
            devices = build_layout(config, standard)
        except PointStandardError as error:
            return [f"expected points: {error}"]
        return expectation_problems(scenario, devices)

    return check_points


def check(expected: ExpectedPoint, devices: Sequence[Device], sources: Sources) -> str | None:
    """None if the snapshot in `sources` meets the expectation, else what it read instead."""
    found = _find(devices, expected)
    if isinstance(found, str):
        return found
    device, row = found
    name = f"{expected.device}.{expected.point}"
    value = resolve_point(device, row, sources)
    if value is None:
        return f"{name} has no value"
    if isinstance(expected.equals, str):
        code = _symbol_code(row, expected.equals)
        if code is None or int(value) != code:
            actual = (row.enum_detail or {}).get(str(int(value)), str(value))
            return f"{name} is {actual}, expected {expected.equals}"
    elif expected.equals is not None and not math.isclose(
        value, expected.equals, abs_tol=max(expected.tolerance, 1e-9)
    ):
        return f"{name} is {value:g}, expected {expected.equals:g} ± {expected.tolerance:g}"
    for symbol in expected.bits_set:
        bit = _bit(row, symbol)
        if bit is None or not int(value) >> bit & 1:
            return f"{name} lacks bit {symbol}"
    for symbol in expected.bits_clear:
        bit = _bit(row, symbol)
        if bit is not None and int(value) >> bit & 1:
            return f"{name} has bit {symbol} set"
    return None


def failures_at(
    scenario: EventScenario, step: int, devices: Sequence[Device], sources: Sources
) -> list[str]:
    """The expectations due at `step` (steps after the start) that the snapshot doesn't meet."""
    failures: list[str] = []
    for expected in scenario.expected_points:
        if expected.from_step <= step <= expected.last_step:
            failure = check(expected, devices, sources)
            if failure is not None:
                failures.append(f"step {step}: {failure}")
    return failures
