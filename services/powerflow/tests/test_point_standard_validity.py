"""The point standard's metadata is valid, and the demo set is what a demo historian can poll.

Invariants guarded:
- every enum and bitfield row matches enums.csv exactly (codes, bits, labels), with scale 1 and no
  unit; bit numbers fit the type; no other row carries a map;
- every numeric row has a scale > 0 and a unit, unless it is dimensionless (power factor, per
  unit, a count); `sign` is set only on signed types;
- the demo set (the `demo` column): at most 15 points per device, all served and recorded, and each
  one actually filled for every device kind that uses its file (no always-zero register);
- at full charge, full discharge and full sun, every demo register of every default site holds its
  value within half a count: nothing saturates.
"""

import asyncio
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import POINT_STANDARD, PROFILES, default_site

from powerflow.core.engine import Engine
from powerflow.core.point_registry import PointRegistry
from powerflow.core.runtime import SiteRuntime
from powerflow.core.setpoints import SetpointService
from powerflow.core.snapshot import Snapshot
from powerflow.models.bess import BessMode, BessSetpoint
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.point_standard import (
    DeviceKind,
    ServerSupport,
    Sources,
    build_layout,
    encode,
    resolver_for,
)
from powerflow.point_standard.catalog import REGISTER_WIDTH, SIGNED_TYPES
from powerflow.point_standard.layout import POINT_LIST_FILE
from powerflow.points import PointSource
from powerflow.settings import SERVICE_ROOT

STANDARD_DIR = SERVICE_ROOT / "docs" / "point-standard"
MAX_DEMO_POINTS = 15
DEFAULT_SITES = ["2bess_1pv", "1bess_1pv", "3bess_2pv"]
ENUM_TYPES = {"enum16"}
BITFIELD_TYPES = {"bitfield16", "bitfield32"}


def raw_rows() -> list[tuple[str, dict[str, str]]]:
    """Every row of every point list, as the CSV has it (columns the catalog doesn't keep too)."""
    rows: list[tuple[str, dict[str, str]]] = []
    for path in sorted(STANDARD_DIR.glob("*.csv")):
        if path.name == "enums.csv":
            continue
        with path.open(encoding="utf-8", newline="") as csv_file:
            rows += [(path.name, row) for row in csv.DictReader(csv_file)]
    return rows


def enum_table() -> dict[str, tuple[str, dict[str, str]]]:
    """enums.csv: enum_ref -> (enum | bitfield, code -> symbol)."""
    table: dict[str, tuple[str, dict[str, str]]] = {}
    with (STANDARD_DIR / "enums.csv").open(encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            kind, codes = table.setdefault(row["enum_ref"], (row["type"], {}))
            assert kind == row["type"], f"{row['enum_ref']} mixes enum and bitfield"
            codes[row["code"]] = row["symbol"]
    return table


ROWS = raw_rows()
NUMERIC_ROWS = [
    (file_name, row)
    for file_name, row in ROWS
    if row["data_type"] in REGISTER_WIDTH and row["data_type"] not in ENUM_TYPES | BITFIELD_TYPES
]


def row_id(item: tuple[str, dict[str, str]]) -> str:
    return f"{item[0]}:{item[1]['point']}"


# Quantities with no unit on purpose: power factors, counts, codes, positions and addresses. A new
# unitless row must be added here deliberately, so a forgotten unit can't slip through.
DIMENSIONLESS_QTYS = {
    "pf", "pf_a", "pf_b", "pf_c", "pf_set", "pf_set_site", "pf_site",
    "cycles", "starts", "trip_count", "op_count", "n_str", "n_str_con", "n_cell_bal",
    "n_inv_avail", "n_inv_run", "n_inv_stby", "n_inv_flt", "n_inv_drt",
    "heartbeat", "ctrl_heartbeat", "fault_code", "set_grp", "shed_prio", "unit_id",
    "tap_pos", "tap_min", "tap_max",
}  # fmt: skip


def dimensionless(row: dict[str, str]) -> bool:
    return row["qty"] in DIMENSIONLESS_QTYS


class TestEnumsAndBitfields:
    @pytest.mark.parametrize(
        "item", [item for item in ROWS if item[1]["data_type"] in ENUM_TYPES], ids=row_id
    )
    def test_an_enum_matches_enums_csv(self, item: tuple[str, dict[str, str]]) -> None:
        _, row = item
        kind, codes = enum_table()[row["enum_ref"]]
        assert kind == "enum"
        assert json.loads(row["enum_detail"]) == codes
        assert (row["scale"], row["unit"], row["bitfield_detail"]) == ("1", "", "")

    @pytest.mark.parametrize(
        "item", [item for item in ROWS if item[1]["data_type"] in BITFIELD_TYPES], ids=row_id
    )
    def test_a_bitfield_matches_enums_csv_and_fits_its_type(
        self, item: tuple[str, dict[str, str]]
    ) -> None:
        _, row = item
        kind, bits = enum_table()[row["enum_ref"]]
        assert kind == "bitfield"
        detail = json.loads(row["bitfield_detail"])
        assert detail == bits
        width_bits = REGISTER_WIDTH[row["data_type"]] * 16
        assert all(key.isdigit() and int(key) < width_bits for key in detail)
        assert (row["scale"], row["unit"], row["enum_detail"]) == ("1", "", "")

    def test_only_enums_and_bitfields_carry_a_map(self) -> None:
        for file_name, row in NUMERIC_ROWS:
            assert not (row["enum_ref"] or row["enum_detail"] or row["bitfield_detail"]), (
                f"{file_name}: {row['point']} is {row['data_type']} but has a map"
            )


class TestNumbers:
    @pytest.mark.parametrize("item", NUMERIC_ROWS, ids=row_id)
    def test_scale_unit_and_sign(self, item: tuple[str, dict[str, str]]) -> None:
        _, row = item
        assert row["scale"] and float(row["scale"]) > 0
        assert row["unit"] or dimensionless(row), "a measurement needs a unit"
        if row["sign"]:
            assert row["data_type"] in SIGNED_TYPES, "a sign convention on an unsigned type"


def demo_rows_by_kind() -> dict[DeviceKind, list[Any]]:
    by_kind: dict[DeviceKind, list[Any]] = defaultdict(list)
    for kind, file_name in POINT_LIST_FILE.items():
        rows = (*POINT_STANDARD.rows(file_name), *POINT_STANDARD.rows("common.csv"))
        by_kind[kind] = [row for row in rows if row.demo]
    return by_kind


class TestDemoSet:
    @pytest.mark.parametrize("kind", list(DeviceKind))
    def test_at_most_15_points_per_device_all_served_and_recorded(self, kind: DeviceKind) -> None:
        rows = demo_rows_by_kind()[kind]
        assert 0 < len(rows) <= MAX_DEMO_POINTS
        for row in rows:
            assert row.support is not ServerSupport.NO, f"{kind}: {row.point} isn't served"
            assert row.record, f"{kind}: {row.point} isn't recorded"
            assert resolver_for(kind, row) is not None, f"{kind}: {row.point} would read 0"

    def test_no_energy_counters(self) -> None:
        for kind, rows in demo_rows_by_kind().items():
            assert not [row.point for row in rows if row.unit.endswith("h")], kind


def site_engine(name: str) -> tuple[Engine, PointRegistry]:
    config = default_site(name)
    simulation = config.simulation.model_copy(
        update={"test_mode": True, "start_time": datetime(2026, 6, 21, 19, tzinfo=UTC)}
    )  # 19:00 UTC: about solar noon at the dev sites
    config = config.model_copy(update={"simulation": simulation})
    engine = Engine(
        SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES
    )
    return engine, PointRegistry(engine, SetpointService(engine))


def sources_for(engine: Engine, registry: PointRegistry, snapshot: Snapshot) -> Sources:
    def read(name: str) -> float | int | bool:
        _, definition = registry.resolve(name)
        if definition.source is PointSource.MEASUREMENT:
            return registry.read_from_snapshot(snapshot, name)
        return registry.read(name)

    return Sources(snapshot, engine.config, read, POINT_STANDARD.enums)


def decode(words: list[int], data_type: str, scale: float) -> float:
    raw = 0
    for word in words:
        raw = (raw << 16) | word
    bits = 16 * len(words)
    if data_type in SIGNED_TYPES and raw >= 1 << (bits - 1):
        raw -= 1 << bits
    return raw * scale


class TestDemoValuesFitTheirRegisters:
    @pytest.mark.parametrize("site", DEFAULT_SITES)
    @pytest.mark.parametrize("direction", [-1, 1], ids=["full_charge", "full_discharge"])
    def test_nothing_saturates(self, site: str, direction: int) -> None:
        engine, registry = site_engine(site)
        for bess in engine.config.bess:
            inverter = bess.inverter
            limit = inverter.p_discharge_max_kw if direction > 0 else inverter.p_charge_max_kw
            engine.setpoints.set_bess(bess.id, BessSetpoint(direction * limit, 0, BessMode.PQ))
        snapshot = asyncio.run(engine.step(2))
        sources = sources_for(engine, registry, snapshot)
        for device in build_layout(engine.config, POINT_STANDARD):
            for register in device.registers:
                if not register.row.demo:
                    continue
                resolver = resolver_for(device.kind, register.row)
                assert resolver is not None
                value = resolver(sources, device)
                assert value is not None, f"{device.label}.{register.row.point} has no value"
                held = decode(
                    encode(float(value), register.row), register.row.data_type, register.row.scale
                )
                assert abs(held - float(value)) <= register.row.scale / 2 + 1e-9, (
                    f"{device.label}.{register.row.point}: {value} doesn't fit"
                )
