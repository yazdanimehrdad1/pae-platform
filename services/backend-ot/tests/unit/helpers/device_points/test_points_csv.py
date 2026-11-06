"""A device's points as CSV: the template, the export, and parsing and planning an import.

Invariants guarded: the columns are the device page's points table (headers and order), and the
old snake_case headers still read; the export is the format the import reads (a round trip changes
nothing); there is no Category column (NATIVE only; a file with one is refused); Size must be the
data type's, registers end by 65535 and a coil is a bool;
every problem of a file is reported with its line and column (required columns and values, types
and choices, address range, labels, duplicate names, overlapping registers, unknown columns),
and a row with a problem is never planned; a row is the whole point (a blank optional cell is its
default or no value); the plan sorts rows into created / updated (with the changed columns, and
"restored" for a deleted point) / unchanged, lists the device's NATIVE points missing from the
file, and refuses a row named like the device's standardized, virtual or profile point.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from helpers.device_points.points_csv import (
    CSV_COLUMNS,
    REQUIRED_COLUMNS,
    format_labels,
    parse_labels,
    parse_points_csv,
    plan_import,
    points_to_csv,
    template_csv,
)

HEADER = ",".join(CSV_COLUMNS)
# The rows below are written in the old snake_case columns (still read), the shortest to type.
LEGACY_HEADER = "name,poll_kind,address,data_type,scale_factor,unit,byte_order,word_order,class,severity,record,labels"


@dataclass
class Stored:
    """An existing point, as the plan reads it."""

    name: str
    address: int = 0
    data_type: str = "int16"
    size: int = 1
    poll_kind: str | None = "holding"
    category: str = "NATIVE"
    scale_factor: float | None = 1.0
    unit: str | None = None
    byte_order: str = "big-endian"
    word_order: str = "msw_first"
    point_class: str | None = None
    severity: str | None = None
    record_enabled: bool = True
    enum_detail: dict[str, str] | None = None
    bitfield_detail: dict[str, str] | None = None
    profile_point_key: str | None = None
    deleted_at: datetime | None = None


def csv_of(*rows: str, header: str = LEGACY_HEADER) -> str:
    return "\r\n".join([header, *rows]) + "\r\n"


def problems_of(text: str) -> list[tuple[int | None, str | None, str]]:
    _, problems = parse_points_csv(text)
    return [(problem.line, problem.column, problem.message) for problem in problems]


class TestTemplateAndExport:
    def test_the_template_is_the_points_table_header(self) -> None:
        assert template_csv() == (
            "Name,Record,Poll Kind,Address,Size,Data Type,Unit,Scale,Byte Order,"
            "Word Order,Class,Severity,Enum / Bit Labels\r\n"
        )
        assert REQUIRED_COLUMNS == ("Name", "Poll Kind", "Address", "Data Type")

    def test_export_lists_active_native_points_by_address(self) -> None:
        points = [
            Stored("W", address=2, unit="kW", scale_factor=0.5, point_class="ANALOG"),
            Stored("InvSt", address=1, data_type="enum16", enum_detail={"3": "RUN", "1": "OFF"}),
            Stored("BESS_ACTIVE_POWER", category="STANDARDIZED"),
            Stored("Gone", address=9, deleted_at=datetime.now(UTC)),
        ]
        lines = points_to_csv(points).splitlines()
        assert lines == [
            HEADER,
            "InvSt,Yes,holding,1,1,enum16,,1,big,msw_first,,,1=OFF; 3=RUN",
            "W,Yes,holding,2,1,int16,kW,0.5,big,msw_first,ANALOG,,",
        ]

    def test_an_exported_file_imports_unchanged(self) -> None:
        points = [
            Stored(
                "Alrm",
                address=4,
                data_type="bitfield32",
                size=2,
                bitfield_detail={"0": "a, b", "31": 'c"d'},
            ),
            Stored(
                "SoC",
                address=3,
                data_type="uint16",
                unit="%",
                scale_factor=0.1,
                record_enabled=False,
            ),
            Stored("W", address=0, byte_order="little", word_order="lsw_first", severity="HIGH"),
        ]
        rows, problems = parse_points_csv(points_to_csv(points))
        assert problems == []
        plan = plan_import(rows, points, delete_missing=False)
        assert [point.name for point in plan.unchanged] == ["W", "SoC", "Alrm"]
        assert not plan.created and not plan.updated and not plan.missing and not plan.problems


class TestParse:
    def test_a_full_row_and_a_minimal_row(self) -> None:
        rows, problems = parse_points_csv(
            csv_of(
                "Alrm,INPUT,10,BITFIELD16,,,little,lsw_first,alarm,high,no,0=A; 15=B",
                "W,holding,0,int16,,,,,,,,",
            )
        )
        assert problems == []
        alarm, power = rows
        assert (alarm.poll_kind, alarm.data_type, alarm.byte_order, alarm.word_order) == (
            "input",
            "bitfield16",
            "little",
            "lsw_first",
        )
        assert (alarm.point_class, alarm.severity, alarm.record_enabled) == ("ALARM", "HIGH", False)
        assert alarm.bitfield_detail == {"0": "A", "15": "B"} and alarm.enum_detail is None
        assert (power.scale_factor, power.unit, power.byte_order, power.record_enabled) == (
            1.0,
            None,
            "big",
            True,
        )
        assert power.size == 1 and alarm.line == 2 and power.line == 3

    def test_the_table_header_with_size(self) -> None:
        rows, problems = parse_points_csv(
            csv_of(
                "W,No,holding,4,2,uint32,kW,0.1,,,,,",
                ",,holding,6,,int16,,,,,,,",
                header=HEADER,
            )
        )
        assert [(problem.line, problem.column, problem.message) for problem in problems] == [
            (3, "Name", "Name is required")
        ]
        assert (rows[0].name, rows[0].size, rows[0].record_enabled, rows[0].unit) == (
            "W",
            2,
            False,
            "kW",
        )

    def test_a_category_column_is_refused(self) -> None:
        assert problems_of(
            "Name,Category,Poll Kind,Address,Data Type\nW,NATIVE,holding,0,int16\n"
        ) == [
            (
                1,
                "Category",
                "remove the Category column: the file holds NATIVE points only (standardized and "
                "virtual points are edited on the device page)",
            )
        ]

    # One bad cell per row (the table's columns), and the message the user sees for it.
    @pytest.mark.parametrize(
        ("row", "column", "message"),
        [
            (",Yes,holding,0,,int16,,,,,,,", "Name", "Name is required"),
            ("W,maybe,holding,0,,int16,,,,,,,", "Record", "Record 'maybe' isn't Yes or No"),
            (
                "W,,coil,0,,int16,,,,,,,",
                "Poll Kind",
                "Poll Kind 'coil' isn't one of holding, input, coils",
            ),
            ("W,,holding,,,int16,,,,,,,", "Address", "Address is required"),
            (
                "W,,holding,-1,,int16,,,,,,,",
                "Address",
                "Address '-1' isn't a whole number from 0 to 65535",
            ),
            (
                "W,,holding,65535,,uint32,,,,,,,",
                "Address",
                "a uint32 at 65535 would run past register 65535",
            ),
            ("W,,holding,0,1,uint32,,,,,,,", "Size", "Size of a uint32 is 2 (or leave it blank)"),
            ("W,,holding,0,,int8,,,,,,,", "Data Type", "Data Type 'int8' isn't one of"),
            ("W,,coils,0,,int16,,,,,,,", "Data Type", "a coil is a bool, not int16"),
            (
                "W,,holding,0,,int16," + "k" * 51 + ",,,,,,",
                "Unit",
                "Unit is longer than 50 characters",
            ),
            ("W,,holding,0,,int16,,x,,,,,", "Scale", "Scale 'x' isn't a number"),
            ("W,,holding,0,,int16,,0,,,,,", "Scale", "Scale can't be 0"),
            (
                "W,,holding,0,,int16,,,middle,,,,",
                "Byte Order",
                "Byte Order 'middle' isn't one of big, little",
            ),
            (
                "W,,holding,0,,int16,,,,first,,,",
                "Word Order",
                "Word Order 'first' isn't one of msw_first, lsw_first",
            ),
            (
                "W,,holding,0,,int16,,,,,FOO,,",
                "Class",
                "Class 'FOO' isn't one of ANALOG, BINARY, ALARM, CONTROL",
            ),
            (
                "W,,holding,0,,int16,,,,,,urgent,",
                "Severity",
                "Severity 'urgent' isn't one of HIGH, MEDIUM, LOW",
            ),
            (
                "W,,holding,0,,int16,,,,,,,0=OFF",
                "Enum / Bit Labels",
                "labels are only for enum and bitfield types",
            ),
            ("W,,holding,0,,bitfield16,,,,,,,16=X", "Enum / Bit Labels", "bit 16 is outside 0-15"),
        ],
    )
    def test_each_column_is_checked(self, row: str, column: str, message: str) -> None:
        problems = problems_of(csv_of(row, header=HEADER))
        assert [(line, problem_column) for line, problem_column, _ in problems] == [(2, column)]
        assert message in problems[0][2]

    def test_columns_in_any_order_case_and_a_bom(self) -> None:
        rows, problems = parse_points_csv("﻿Address,NAME,data_type,Poll_Kind\n5,W,uint32,holding\n")
        assert problems == []
        assert (rows[0].name, rows[0].address, rows[0].size) == ("W", 5, 2)

    def test_quoted_cells(self) -> None:
        rows, problems = parse_points_csv(
            csv_of('"P, 1",holding,0,enum16,,"k,W",,,,,,"0=OFF; 1=""ON"""')
        )
        assert problems == []
        assert (rows[0].name, rows[0].unit, rows[0].enum_detail) == (
            "P, 1",
            "k,W",
            {"0": "OFF", "1": '"ON"'},
        )

    def test_every_problem_is_reported_with_its_line_and_column(self) -> None:
        problems = problems_of(
            csv_of(
                ",coil,70000,int8,x,,middle,first,FOO,urgent,maybe,",
                "W,holding,0,int16,0,,,,,,,0=OFF",
            )
        )
        assert [(line, column) for line, column, _ in problems] == [
            (2, "Name"),
            (2, "Record"),
            (2, "Poll Kind"),
            (2, "Address"),
            (2, "Data Type"),
            (2, "Scale"),
            (2, "Byte Order"),
            (2, "Word Order"),
            (2, "Class"),
            (2, "Severity"),
            (3, "Scale"),
            (3, "Enum / Bit Labels"),
        ]

    def test_header_problems(self) -> None:
        assert problems_of("name,addres,data_type\nW,0,int16\n") == [
            (1, None, "unknown column(s) addres; the columns are " + ", ".join(CSV_COLUMNS)),
            (1, None, "missing required column(s): Poll Kind, Address"),
        ]
        assert problems_of("") == [(None, None, "the file is empty")]
        assert problems_of(HEADER + "\n\n") == [(None, None, "the file has no points")]

    def test_duplicate_names_and_too_many_cells(self) -> None:
        problems = problems_of(
            csv_of("W,holding,0,int16", "W,holding,1,int16", "X,holding,2,int16,,,,,,,,,extra")
        )
        assert problems == [
            (4, None, "13 cells but 12 columns"),
            (3, "Name", "'W' is also on line 2"),
        ]


class TestLabels:
    def test_round_trip_sorted_by_code(self) -> None:
        assert format_labels({"10": "B", "2": "A"}) == "2=A; 10=B"
        assert parse_labels("2=A; 10=B", "enum16") == ({"2": "A", "10": "B"}, None)
        assert parse_labels("2=A\n03=C", "enum16") == ({"2": "A", "3": "C"}, None)
        assert parse_labels("  ", "enum16") == (None, None)

    @pytest.mark.parametrize(
        ("text", "data_type", "message"),
        [
            ("16=X", "bitfield16", "bit 16 is outside 0-15"),
            ("31=X", "bitfield32", None),
            ("65536=X", "enum16", "code 65536 is outside 0-65535"),
            ("OFF", "enum16", "isn't <code>=<label>"),
            ("1=", "enum16", "code 1 has no label"),
            ("1=A; 01=B", "enum16", "code 1 is listed twice"),
            ("1=A", "int16", "labels are only for enum and bitfield types"),
        ],
    )
    def test_problems(self, text: str, data_type: str, message: str | None) -> None:
        _, error = parse_labels(text, data_type)
        assert (error is None) if message is None else (message in (error or ""))


class TestPlan:
    def rows(self, *lines: str):
        rows, problems = parse_points_csv(csv_of(*lines))
        assert problems == []
        return rows

    def test_created_updated_unchanged_and_missing(self) -> None:
        existing = [
            Stored("W", address=0, unit="kW"),
            Stored("Var", address=1),
            Stored("Old", address=9),
            Stored("Restored", address=3, deleted_at=datetime.now(UTC)),
            Stored("BESS_ACTIVE_POWER", category="STANDARDIZED"),
            Stored("Profile", address=20, profile_point_key="rte"),
        ]
        plan = plan_import(
            self.rows(
                "W,holding,0,int16,,kW,,,,,,",
                "Var,holding,1,int16,,,,,,,no,",
                "New,input,0,uint16,,,,,,,,",
                "Restored,holding,3,int16,,,,,,,,",
            ),
            existing,
            delete_missing=False,
        )
        assert [point.name for point in plan.unchanged] == ["W"]
        assert [(point.name, fields) for point, fields in plan.updated] == [
            ("Var", ["Record"]),
            ("Restored", ["restored"]),
        ]
        assert [point.name for point in plan.created] == ["New"]
        assert plan.missing == ["Old"]  # not the standardized, profile or deleted points
        assert plan.problems == []

    def test_a_repeated_name_is_planned_once(self) -> None:
        rows, problems = parse_points_csv(csv_of("W,holding,0,int16", "W,holding,5,int16"))
        assert [problem.column for problem in problems] == ["Name"]
        plan = plan_import(rows, [Stored("W")], delete_missing=False)
        assert [point.name for point in plan.unchanged] == ["W"] and plan.updated == []

    def test_a_blank_cell_clears_a_value(self) -> None:
        plan = plan_import(
            self.rows("W,holding,0,int16,,,,,,,,"),
            [Stored("W", unit="kW", scale_factor=0.1, point_class="ANALOG")],
            delete_missing=False,
        )
        assert plan.updated[0][1] == ["Scale", "Unit", "Class"]

    def test_a_row_named_like_a_standardized_or_profile_point_is_refused(self) -> None:
        plan = plan_import(
            self.rows("BESS_ACTIVE_POWER,holding,0,int16", "Profile,holding,1,int16"),
            [
                Stored("BESS_ACTIVE_POWER", category="STANDARDIZED"),
                Stored("Profile", address=5, profile_point_key="k"),
            ],
            delete_missing=False,
        )
        assert [(problem.line, problem.column) for problem in plan.problems] == [
            (2, "Name"),
            (3, "Name"),
        ]
        assert not plan.created and not plan.updated

    def test_overlaps_within_the_file_and_with_points_that_stay(self) -> None:
        rows = self.rows(
            "A,holding,10,uint32,,,,,,,,",  # 10-11
            "B,holding,11,int16,,,,,,,,",  # overlaps A
            "C,input,11,int16,,,,,,,,",  # input: a separate address space
            "D,holding,20,int16,,,,,,,,",  # overlaps Kept (not in the file)
        )
        existing = [Stored("Kept", address=20)]
        kept = plan_import(rows, existing, delete_missing=False)
        assert [(problem.line, problem.column) for problem in kept.problems] == [
            (3, "Address"),
            (5, "Address"),
        ]
        assert "'B' (holding 11-11) overlaps 'A' (10-11, line 2)" in kept.problems[0].message
        assert "a point already on the device" in kept.problems[1].message
        deleting = plan_import(rows, existing, delete_missing=True)
        assert [problem.line for problem in deleting.problems] == [3]  # Kept is going away
