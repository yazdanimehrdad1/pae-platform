"""The PAE point standard (docs/point-standard/*.csv), loaded and validated.

Each asset CSV row becomes a `PointRow`. Rows the Modbus server can never serve are dropped:
string rows (identity text is 8-16 registers each and doesn't fit a 100-register device chunk).
A repeated row (`POAI_<n>`, `DCA_<n>`, ...) is expanded to its first instance (`POAI_1`).
"""

import csv
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from powerflow.errors import PointStandardError

ENUMS_FILE = "enums.csv"
COMMON_FILE = "common.csv"
REPEAT_SUFFIX = "_<n>"

# Registers per data type (16-bit words).
REGISTER_WIDTH: dict[str, int] = {
    "int16": 1,
    "uint16": 1,
    "enum16": 1,
    "bitfield16": 1,
    "int32": 2,
    "uint32": 2,
    "bitfield32": 2,
    "uint64": 4,
}
SIGNED_TYPES = {"int16", "int32"}


class ServerSupport(StrEnum):
    """The `powerflow_server` column: can the powerflow Modbus server fill this point?"""

    YES = "yes"  # read straight from a simulation result (times a unit factor)
    CALC = "calc"  # derived from simulation results (see point_standard/calc.py)
    NO = "no"  # not simulated; the register reads 0


@dataclass(frozen=True)
class PointRow:
    point: str
    data_type: str
    scale: float
    unit: str
    support: ServerSupport
    enum_detail: dict[str, str] | None = None  # value → label (enum points)
    bitfield_detail: dict[str, str] | None = None  # bit number → label (bitfield points)
    label: str = ""  # the CSV's human-readable name
    qty: str = ""  # the physical quantity key, the same across asset types (e.g. v_ab)
    tier: str = ""  # M mandatory, R recommended, O optional

    @property
    def width(self) -> int:
        return REGISTER_WIDTH[self.data_type]

    @property
    def signed(self) -> bool:
        return self.data_type in SIGNED_TYPES


class EnumTable:
    """enums.csv: `(enum_ref, symbol) → code`. Calc code names SunSpec/PAE codes by symbol, so
    the numbers live in one place (the standard) and can't drift."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._codes = {(row["enum_ref"], row["symbol"]): int(row["code"]) for row in rows}

    def code(self, enum_ref: str, symbol: str) -> int:
        try:
            return self._codes[(enum_ref, symbol)]
        except KeyError as error:
            raise PointStandardError(f"{enum_ref} has no symbol {symbol!r}") from error

    def bits(self, enum_ref: str, *symbols: str) -> int:
        """A bitfield value with the named bits set."""
        value = 0
        for symbol in symbols:
            value |= 1 << self.code(enum_ref, symbol)
        return value


@dataclass(frozen=True)
class PointStandard:
    point_lists: dict[str, tuple[PointRow, ...]]  # file name → rows, in CSV order
    enums: EnumTable

    def rows(self, file_name: str) -> tuple[PointRow, ...]:
        return self.point_lists[file_name]


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as csv_file:
            return list(csv.DictReader(csv_file))
    except OSError as error:
        raise PointStandardError(f"can't read {path}: {error}") from error


def _detail(path: Path, raw: dict[str, str], column: str) -> dict[str, str] | None:
    text = raw.get(column, "")
    if not text:
        return None
    try:
        detail = json.loads(text)
    except json.JSONDecodeError as error:
        raise PointStandardError(f"{path.name}: {raw['point']}: {column} isn't JSON") from error
    if not isinstance(detail, dict):
        raise PointStandardError(f"{path.name}: {raw['point']}: {column} must be a JSON object")
    return {str(key): str(value) for key, value in detail.items()}


def _point_row(path: Path, raw: dict[str, str]) -> PointRow | None:
    if raw["data_type"].startswith("string"):
        return None
    if raw["data_type"] not in REGISTER_WIDTH:
        raise PointStandardError(f"{path.name}: {raw['point']}: unknown type {raw['data_type']}")
    try:
        support = ServerSupport(raw.get("powerflow_server", ""))
    except ValueError as error:
        raise PointStandardError(
            f"{path.name}: {raw['point']}: powerflow_server must be yes, calc or no"
        ) from error
    point = raw["point"]
    if point.endswith(REPEAT_SUFFIX):
        point = point.removesuffix(REPEAT_SUFFIX) + "_1"
    return PointRow(
        point=point,
        data_type=raw["data_type"],
        scale=float(raw["scale"] or 1),
        unit=raw["unit"],
        support=support,
        enum_detail=_detail(path, raw, "enum_detail"),
        bitfield_detail=_detail(path, raw, "bitfield_detail"),
        label=raw.get("label", ""),
        qty=raw.get("qty", ""),
        tier=raw.get("tier", ""),
    )


def load_point_standard(directory: Path) -> PointStandard:
    """Read every point list and the enum table. Raises PointStandardError on a bad file."""
    point_lists: dict[str, tuple[PointRow, ...]] = {}
    for path in sorted(directory.glob("*.csv")):
        if path.name == ENUMS_FILE:
            continue
        rows = [row for raw in _read_csv(path) if (row := _point_row(path, raw)) is not None]
        names = [row.point for row in rows]
        if len(names) != len(set(names)):
            raise PointStandardError(f"{path.name}: duplicate point names")
        point_lists[path.name] = tuple(rows)
    if COMMON_FILE not in point_lists:
        raise PointStandardError(f"{directory} has no {COMMON_FILE}")
    return PointStandard(point_lists, EnumTable(_read_csv(directory / ENUMS_FILE)))
