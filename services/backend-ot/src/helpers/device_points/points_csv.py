"""A device's NATIVE points as CSV: the template, the export, and the parse + plan of an import.

Pure: no database. The file holds NATIVE points only, so there is no Category column (a file with
one is refused); the other columns are the device page's points table, in its order and with its
headers (the old snake_case names, e.g. `poll_kind`, are read too). One row is one whole point. A
blank optional cell means the default (recorded, scale 1, big, msw_first, the data type's size)
or no value (unit, class, severity, labels), so an import can clear a value.

    Name*, Record, Poll Kind*, Address*, Size, Data Type*, Unit, Scale, Byte Order, Word Order,
    Class, Severity, Enum / Bit Labels

Size must be the data type's size, the registers must end by 65535, and a coil is a bool. "Enum /
Bit Labels" is the table's text: "0=OFF; 3=RUNNING" (enum codes or bitfield bits), only on enum
and bitfield types. Every problem of a file is collected, each with its line and column, so a
user can fix them all at once; nothing is applied while there is one.
"""

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast, get_args

from schemas.api_models.types import (
    SUPPORTED_DATA_TYPES,
    DataType,
    PointClass,
    Severity,
    register_size,
)

# (field, header): the device page's points table (web-plusdas DevicePointsGrid), same order.
COLUMNS: tuple[tuple[str, str], ...] = (
    ("name", "Name"),
    ("record", "Record"),
    ("poll_kind", "Poll Kind"),
    ("address", "Address"),
    ("size", "Size"),
    ("data_type", "Data Type"),
    ("unit", "Unit"),
    ("scale_factor", "Scale"),
    ("byte_order", "Byte Order"),
    ("word_order", "Word Order"),
    ("class", "Class"),
    ("severity", "Severity"),
    ("labels", "Enum / Bit Labels"),
)
HEADERS: dict[str, str] = dict(COLUMNS)
CSV_COLUMNS: tuple[str, ...] = tuple(header for _, header in COLUMNS)
REQUIRED_FIELDS: tuple[str, ...] = ("name", "poll_kind", "address", "data_type")
REQUIRED_COLUMNS: tuple[str, ...] = tuple(HEADERS[name] for name in REQUIRED_FIELDS)


def _header_key(header: str) -> str:
    """ "Poll Kind", "poll_kind" and "POLL KIND" alike: lower case, words joined by "_"."""
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")


# A header cell to its field: the table's header, or the field's own name.
_FIELD_BY_HEADER: dict[str, str] = {
    **{_header_key(header): name for name, header in COLUMNS},
    **{name: name for name, _ in COLUMNS},
}
# Larger files are refused before parsing (the request body limit is the router's).
MAX_ROWS = 2000
MAX_ADDRESS = 65535
MAX_NAME_LENGTH = 255
MAX_UNIT_LENGTH = 50

PollKind = Literal["holding", "input", "coils"]
POLL_KINDS: tuple[str, ...] = get_args(PollKind)
POINT_CLASSES: tuple[str, ...] = get_args(PointClass)
SEVERITIES: tuple[str, ...] = get_args(Severity)
BYTE_ORDERS = ("big", "little")
WORD_ORDERS = ("msw_first", "lsw_first")
RECORD_VALUES = {"yes": True, "no": False, "true": True, "false": False, "1": True, "0": False}
LABEL_SEPARATOR = "; "
# The fields compared to tell a changed point from an unchanged one (CSV names).
COMPARED_FIELDS: tuple[str, ...] = (
    "poll_kind",
    "address",
    "data_type",
    "scale_factor",
    "unit",
    "byte_order",
    "word_order",
    "class",
    "severity",
    "record",
    "labels",
)


@dataclass(frozen=True)
class CsvProblem:
    line: int | None  # 1 = the header
    column: str | None
    message: str


@dataclass(frozen=True)
class CsvPoint:
    """One parsed, valid row: a whole NATIVE point."""

    line: int
    name: str
    poll_kind: PollKind
    address: int
    data_type: DataType
    scale_factor: float
    unit: str | None
    byte_order: str
    word_order: str
    point_class: PointClass | None
    severity: Severity | None
    record_enabled: bool
    enum_detail: dict[str, str] | None
    bitfield_detail: dict[str, str] | None

    @property
    def size(self) -> int:
        return register_size(self.data_type)


class StoredPoint(Protocol):
    """What the plan reads of an existing point (the ORM row or a response model)."""

    @property
    def name(self) -> str: ...
    @property
    def category(self) -> str: ...
    @property
    def poll_kind(self) -> str | None: ...
    @property
    def address(self) -> int: ...
    @property
    def size(self) -> int: ...
    @property
    def data_type(self) -> str: ...
    @property
    def scale_factor(self) -> float | None: ...
    @property
    def unit(self) -> str | None: ...
    @property
    def byte_order(self) -> str: ...
    @property
    def word_order(self) -> str: ...
    @property
    def point_class(self) -> str | None: ...
    @property
    def severity(self) -> str | None: ...
    @property
    def record_enabled(self) -> bool: ...
    @property
    def enum_detail(self) -> dict[str, str] | None: ...
    @property
    def bitfield_detail(self) -> dict[str, str] | None: ...
    @property
    def profile_point_key(self) -> str | None: ...
    @property
    def deleted_at(self) -> object | None: ...


@dataclass
class ImportPlan:
    created: list[CsvPoint] = field(default_factory=list)
    updated: list[tuple[CsvPoint, list[str]]] = field(default_factory=list)  # point, changed fields
    unchanged: list[CsvPoint] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # active NATIVE points not in the file
    problems: list[CsvProblem] = field(default_factory=list)


# ---------------------------------------------------------------------------- labels


def label_kind(data_type: str) -> Literal["enum", "bitfield"] | None:
    if data_type.startswith("enum"):
        return "enum"
    if data_type.startswith("bitfield"):
        return "bitfield"
    return None


def _max_label_key(data_type: str) -> int:
    bits = 16 * register_size(cast(DataType, data_type))
    return bits - 1 if label_kind(data_type) == "bitfield" else (1 << bits) - 1


def format_labels(detail: dict[str, str] | None) -> str:
    if not detail:
        return ""
    keys = sorted(
        detail, key=lambda key: (not key.isdigit(), int(key) if key.isdigit() else 0, key)
    )
    return LABEL_SEPARATOR.join(f"{key}={detail[key]}" for key in keys)


def parse_labels(text: str, data_type: str) -> tuple[dict[str, str] | None, str | None]:
    """The labels map, or an error message. Blank = no labels."""
    if not text.strip():
        return None, None
    kind = label_kind(data_type)
    if kind is None:
        return None, f"labels are only for enum and bitfield types, not {data_type}"
    maximum = _max_label_key(data_type)
    noun = "bit" if kind == "bitfield" else "code"
    labels: dict[str, str] = {}
    for part in text.replace("\n", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        key, separator, label = part.partition("=")
        key, label = key.strip(), label.strip()
        if not separator or not key.isdigit():
            return None, f"'{part}' isn't <{noun}>=<label> (e.g. 0=OFF; 3=RUNNING)"
        if int(key) > maximum:
            return None, f"{noun} {int(key)} is outside 0-{maximum} for {data_type}"
        if not label:
            return None, f"{noun} {int(key)} has no label"
        if str(int(key)) in labels:
            return None, f"{noun} {int(key)} is listed twice"
        labels[str(int(key))] = label
    return labels or None, None


# ---------------------------------------------------------------------------- export


def _byte_order(value: str | None) -> str:
    """The decoder reads only "little" as little-endian; anything else is big."""
    return "little" if value == "little" else "big"


def _word_order(value: str | None) -> str:
    return "lsw_first" if value == "lsw_first" else "msw_first"


def _number(value: float) -> str:
    return f"{value:g}" if abs(value) < 1e15 else repr(value)


def _point_values(point: StoredPoint) -> dict[str, str]:
    detail = point.enum_detail if label_kind(point.data_type) == "enum" else point.bitfield_detail
    return {
        "name": point.name,
        "record": "Yes" if point.record_enabled else "No",
        "poll_kind": point.poll_kind or "",
        "address": str(point.address),
        "size": str(point.size),
        "data_type": point.data_type,
        "unit": point.unit or "",
        "scale_factor": _number(point.scale_factor if point.scale_factor is not None else 1.0),
        "byte_order": _byte_order(point.byte_order),
        "word_order": _word_order(point.word_order),
        "class": point.point_class or "",
        "severity": point.severity or "",
        "labels": format_labels(detail if label_kind(point.data_type) else None),
    }


def _write(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    writer.writerows([row[name] for name, _ in COLUMNS] for row in rows)
    return buffer.getvalue()


def template_csv() -> str:
    """The header row only."""
    return _write([])


def points_to_csv(points: list[StoredPoint]) -> str:
    """The device's active NATIVE points, by poll kind then address."""
    native = [p for p in points if p.category == "NATIVE" and p.deleted_at is None]
    native.sort(key=lambda p: (p.poll_kind or "", p.address, p.name))
    return _write([_point_values(point) for point in native])


# ---------------------------------------------------------------------------- parse


def _choice(
    raw: str, allowed: tuple[str, ...], field_name: str, *, upper: bool = False
) -> tuple[str | None, str | None]:
    value = raw.strip().upper() if upper else raw.strip().lower()
    if not value:
        return None, None
    if value not in allowed:
        return None, f"{HEADERS[field_name]} '{raw.strip()}' isn't one of {', '.join(allowed)}"
    return value, None


def _parse_row(line: int, raw: dict[str, str], problems: list[CsvProblem]) -> CsvPoint | None:
    def problem(field_name: str, message: str) -> None:
        problems.append(CsvProblem(line, HEADERS[field_name], message))

    count = len(problems)
    name = raw.get("name", "").strip()
    if not name:
        problem("name", "Name is required")
    elif len(name) > MAX_NAME_LENGTH:
        problem("name", f"Name is longer than {MAX_NAME_LENGTH} characters")

    record_text = raw.get("record", "").strip().lower()
    record_enabled = True
    if record_text:
        if record_text not in RECORD_VALUES:
            problem("record", f"Record '{raw.get('record', '').strip()}' isn't Yes or No")
        else:
            record_enabled = RECORD_VALUES[record_text]

    poll_kind, error = _choice(raw.get("poll_kind", ""), POLL_KINDS, "poll_kind")
    if error:
        problem("poll_kind", error)
    elif poll_kind is None:
        problem("poll_kind", "Poll Kind is required (holding, input or coils)")

    address: int | None = None
    address_text = raw.get("address", "").strip()
    if not address_text:
        problem("address", "Address is required")
    elif not address_text.isdigit() or int(address_text) > MAX_ADDRESS:
        problem("address", f"Address '{address_text}' isn't a whole number from 0 to {MAX_ADDRESS}")
    else:
        address = int(address_text)

    data_type_text = raw.get("data_type", "").strip().lower()
    if not data_type_text:
        problem("data_type", "Data Type is required")
    elif data_type_text not in SUPPORTED_DATA_TYPES:
        problem(
            "data_type",
            f"Data Type '{data_type_text}' isn't one of {', '.join(sorted(SUPPORTED_DATA_TYPES))}",
        )

    # The size follows from the data type; a filled-in Size must agree with it.
    size_text = raw.get("size", "").strip()
    if data_type_text in SUPPORTED_DATA_TYPES:
        expected = register_size(cast(DataType, data_type_text))
        if size_text and (not size_text.isdigit() or int(size_text) != expected):
            problem("size", f"Size of a {data_type_text} is {expected} (or leave it blank)")
        if address is not None and address + expected - 1 > MAX_ADDRESS:
            problem(
                "address",
                f"a {data_type_text} at {address} would run past register {MAX_ADDRESS}",
            )
        # A coil is one bit: the poller reads coils as on/off.
        if poll_kind == "coils" and data_type_text != "bool":
            problem("data_type", f"a coil is a bool, not {data_type_text}")

    unit = raw.get("unit", "").strip() or None
    if unit is not None and len(unit) > MAX_UNIT_LENGTH:
        problem("unit", f"Unit is longer than {MAX_UNIT_LENGTH} characters")

    scale_factor = 1.0
    scale_text = raw.get("scale_factor", "").strip()
    if scale_text:
        try:
            scale_factor = float(scale_text)
        except ValueError:
            problem("scale_factor", f"Scale '{scale_text}' isn't a number")
        else:
            if scale_factor != scale_factor or scale_factor in (float("inf"), float("-inf")):
                problem("scale_factor", "Scale must be a finite number")
            elif scale_factor == 0:
                problem("scale_factor", "Scale can't be 0")

    byte_order, error = _choice(raw.get("byte_order", ""), BYTE_ORDERS, "byte_order")
    if error:
        problem("byte_order", error)
    word_order, error = _choice(raw.get("word_order", ""), WORD_ORDERS, "word_order")
    if error:
        problem("word_order", error)
    point_class, error = _choice(raw.get("class", ""), POINT_CLASSES, "class", upper=True)
    if error:
        problem("class", error)
    severity, error = _choice(raw.get("severity", ""), SEVERITIES, "severity", upper=True)
    if error:
        problem("severity", error)

    enum_detail: dict[str, str] | None = None
    bitfield_detail: dict[str, str] | None = None
    if data_type_text in SUPPORTED_DATA_TYPES:
        labels, error = parse_labels(raw.get("labels", ""), data_type_text)
        if error:
            problem("labels", error)
        elif label_kind(data_type_text) == "enum":
            enum_detail = labels
        elif label_kind(data_type_text) == "bitfield":
            bitfield_detail = labels

    if len(problems) > count or address is None or poll_kind is None:
        return None
    return CsvPoint(
        line=line,
        name=name,
        poll_kind=cast(PollKind, poll_kind),
        address=address,
        data_type=cast(DataType, data_type_text),
        scale_factor=scale_factor,
        unit=unit,
        byte_order=byte_order or "big",
        word_order=word_order or "msw_first",
        point_class=cast(PointClass | None, point_class),
        severity=cast(Severity | None, severity),
        record_enabled=record_enabled,
        enum_detail=enum_detail,
        bitfield_detail=bitfield_detail,
    )


def parse_points_csv(text: str) -> tuple[list[CsvPoint], list[CsvProblem]]:
    """Every valid row and every problem of the file (rows with a problem aren't returned)."""
    text = text.removeprefix("﻿")  # Excel's UTF-8 byte order mark
    if not text.strip():
        return [], [CsvProblem(None, None, "the file is empty")]
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except csv.Error as error:
        return [], [CsvProblem(1, None, f"the header can't be read: {error}")]
    # Each header cell's field ("" for a blank header cell, None for an unknown one).
    columns = [_FIELD_BY_HEADER.get(_header_key(cell)) if cell.strip() else "" for cell in header]
    problems: list[CsvProblem] = []
    unknown = [cell.strip() for cell, column in zip(header, columns, strict=True) if column is None]
    if any(_header_key(cell) == "category" for cell in unknown):
        problems.append(
            CsvProblem(
                1,
                "Category",
                "remove the Category column: the file holds NATIVE points only (standardized and "
                "virtual points are edited on the device page)",
            )
        )
        unknown = [cell for cell in unknown if _header_key(cell) != "category"]
    if unknown:
        problems.append(
            CsvProblem(
                1,
                None,
                f"unknown column(s) {', '.join(unknown)}; the columns are {', '.join(CSV_COLUMNS)}",
            )
        )
    duplicated = [HEADERS[name] for name, _ in COLUMNS if columns.count(name) > 1]
    if duplicated:
        problems.append(CsvProblem(1, None, f"column(s) listed twice: {', '.join(duplicated)}"))
    missing = [HEADERS[name] for name in REQUIRED_FIELDS if name not in columns]
    if missing:
        problems.append(CsvProblem(1, None, f"missing required column(s): {', '.join(missing)}"))
    if problems:
        return [], problems

    points: list[CsvPoint] = []
    rows = 0
    try:
        for cells in reader:
            if not any(cell.strip() for cell in cells):
                continue
            rows += 1
            if rows > MAX_ROWS:
                problems.append(CsvProblem(reader.line_num, None, f"more than {MAX_ROWS} rows"))
                break
            if len(cells) > len(columns):
                problems.append(
                    CsvProblem(
                        reader.line_num, None, f"{len(cells)} cells but {len(columns)} columns"
                    )
                )
                continue
            raw = {
                column: cells[index] if index < len(cells) else ""
                for index, column in enumerate(columns)
                if column
            }
            point = _parse_row(reader.line_num, raw, problems)
            if point is not None:
                points.append(point)
    except csv.Error as error:
        problems.append(CsvProblem(reader.line_num, None, f"the file can't be read: {error}"))
    if rows == 0 and not problems:
        problems.append(CsvProblem(None, None, "the file has no points"))

    first_line: dict[str, int] = {}
    for point in points:
        if point.name in first_line:
            problems.append(
                CsvProblem(
                    point.line,
                    HEADERS["name"],
                    f"'{point.name}' is also on line {first_line[point.name]}",
                )
            )
        else:
            first_line[point.name] = point.line
    return points, problems


# ---------------------------------------------------------------------------- plan


def _stored_values(point: StoredPoint) -> dict[str, object]:
    kind = label_kind(point.data_type)
    return {
        "poll_kind": point.poll_kind,
        "address": point.address,
        "data_type": point.data_type,
        "scale_factor": point.scale_factor if point.scale_factor is not None else 1.0,
        "unit": point.unit or None,
        "byte_order": _byte_order(point.byte_order),
        "word_order": _word_order(point.word_order),
        "class": point.point_class,
        "severity": point.severity,
        "record": point.record_enabled,
        "labels": (point.enum_detail if kind == "enum" else point.bitfield_detail if kind else None)
        or None,
    }


def _csv_values(point: CsvPoint) -> dict[str, object]:
    return {
        "poll_kind": point.poll_kind,
        "address": point.address,
        "data_type": point.data_type,
        "scale_factor": point.scale_factor,
        "unit": point.unit,
        "byte_order": point.byte_order,
        "word_order": point.word_order,
        "class": point.point_class,
        "severity": point.severity,
        "record": point.record_enabled,
        "labels": point.enum_detail or point.bitfield_detail,
    }


def changed_fields(stored: StoredPoint, point: CsvPoint) -> list[str]:
    before, after = _stored_values(stored), _csv_values(point)
    return [HEADERS[name] for name in COMPARED_FIELDS if before[name] != after[name]]


@dataclass(frozen=True)
class _Range:
    name: str
    poll_kind: str
    first: int
    last: int
    line: int | None  # None: a point already on the device


def _overlap_problems(ranges: list[_Range]) -> list[CsvProblem]:
    problems: list[CsvProblem] = []
    by_kind: dict[str, list[_Range]] = defaultdict(list)
    for item in ranges:
        by_kind[item.poll_kind].append(item)
    for kind, group in by_kind.items():
        group.sort(key=lambda item: (item.first, item.line or 0))
        for index, current in enumerate(group):
            for previous in group[:index]:
                if previous.last < current.first:
                    continue
                culprit, other = (
                    (current, previous) if current.line is not None else (previous, current)
                )
                if culprit.line is None:
                    continue
                where = (
                    "a point already on the device" if other.line is None else f"line {other.line}"
                )
                problems.append(
                    CsvProblem(
                        culprit.line,
                        HEADERS["address"],
                        f"'{culprit.name}' ({kind} {culprit.first}-{culprit.last}) overlaps "
                        f"'{other.name}' ({other.first}-{other.last}, {where})",
                    )
                )
    return problems


def plan_import(
    points: list[CsvPoint], existing: list[StoredPoint], *, delete_missing: bool
) -> ImportPlan:
    """What importing `points` onto a device with `existing` points would do.

    Problems: a row named like the device's standardized, virtual or profile point (those aren't
    NATIVE points the file can set), and registers that would overlap, among the file's rows or
    with a NATIVE point the import leaves in place."""
    plan = ImportPlan()
    by_name = {point.name: point for point in existing}
    in_file = {point.name for point in points}

    planned: set[str] = set()
    for point in points:
        if point.name in planned:
            continue  # a repeated name is the parser's problem; plan the first row only
        planned.add(point.name)
        stored = by_name.get(point.name)
        if stored is not None and (stored.category != "NATIVE" or stored.profile_point_key):
            owner = "the site profile's" if stored.profile_point_key else f"a {stored.category}"
            plan.problems.append(
                CsvProblem(
                    point.line,
                    HEADERS["name"],
                    f"'{point.name}' is {owner} point on this device; rename the row",
                )
            )
            continue
        if stored is None:
            plan.created.append(point)
        elif stored.deleted_at is not None:
            plan.updated.append((point, ["restored", *changed_fields(stored, point)]))
        elif changes := changed_fields(stored, point):
            plan.updated.append((point, changes))
        else:
            plan.unchanged.append(point)

    plan.missing = sorted(
        point.name
        for point in existing
        if point.category == "NATIVE"
        and point.deleted_at is None
        and not point.profile_point_key
        and point.name not in in_file
    )
    kept = [
        _Range(
            point.name, point.poll_kind or "", point.address, point.address + point.size - 1, None
        )
        for point in existing
        if point.category == "NATIVE"
        and point.deleted_at is None
        and point.name not in in_file
        and not (delete_missing and point.name in plan.missing)
    ]
    incoming = [
        _Range(
            point.name, point.poll_kind, point.address, point.address + point.size - 1, point.line
        )
        for point in points
    ]
    plan.problems += _overlap_problems(kept + incoming)
    return plan
