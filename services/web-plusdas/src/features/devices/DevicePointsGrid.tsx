import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus, Save, Trash2, Undo2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  DevicePoint, DevicePointClass, DevicePointCreateRequest, DevicePointDataType, DevicePointSeverity,
  DevicePointUpdateRequest,
} from "@/shared/types/device-point";

type ColumnKey =
  | "name" | "category" | "poll_kind" | "address" | "size" | "data_type"
  | "unit" | "scale_factor" | "byte_order" | "word_order" | "class" | "severity";

type ColumnKind = "text" | "number" | "enum";

interface Column {
  key: ColumnKey;
  label: string;
  kind: ColumnKind;
  options?: string[];
  minWidth: string;
}

const CATEGORY = ["NATIVE", "STANDARDIZED", "VIRTUAL"];
const POLL_KIND = ["holding", "input", "coils"];
// Every data type backend-ot accepts (its contract enum), common ones first. A Record, so a
// contract change fails the typecheck until this list matches.
const DATA_TYPES: Record<DevicePointDataType, true> = {
  int16: true, uint16: true, int32: true, uint32: true, float32: true, float64: true,
  int64: true, uint64: true, bool: true, raw: true, enum16: true, enum32: true,
  bitfield16: true, bitfield32: true, status_word16: true, status_word32: true,
};
const DATA_TYPE = Object.keys(DATA_TYPES) as DevicePointDataType[];
// Point class / severity (contract enums, optional). Records, so a contract change fails the typecheck.
const POINT_CLASSES: Record<DevicePointClass, true> = { ANALOG: true, BINARY: true, ALARM: true, CONTROL: true };
const POINT_CLASS = Object.keys(POINT_CLASSES) as DevicePointClass[];
const SEVERITIES: Record<DevicePointSeverity, true> = { HIGH: true, MEDIUM: true, LOW: true };
const SEVERITY = Object.keys(SEVERITIES) as DevicePointSeverity[];
// Enum columns that may be left empty.
const OPTIONAL_ENUM_COLUMNS: ColumnKey[] = ["poll_kind", "class", "severity"];
const BYTE_ORDER = ["big", "little"];
const WORD_ORDER = ["msw_first", "lsw_first"];

const COLUMNS: Column[] = [
  { key: "name", label: "Name", kind: "text", minWidth: "min-w-[150px]" },
  { key: "category", label: "Category", kind: "enum", options: CATEGORY, minWidth: "min-w-[130px]" },
  { key: "poll_kind", label: "Poll Kind", kind: "enum", options: POLL_KIND, minWidth: "min-w-[110px]" },
  { key: "address", label: "Address", kind: "number", minWidth: "min-w-[90px]" },
  { key: "size", label: "Size", kind: "number", minWidth: "min-w-[70px]" },
  { key: "data_type", label: "Data Type", kind: "enum", options: DATA_TYPE, minWidth: "min-w-[110px]" },
  { key: "unit", label: "Unit", kind: "text", minWidth: "min-w-[80px]" },
  { key: "scale_factor", label: "Scale", kind: "number", minWidth: "min-w-[80px]" },
  { key: "byte_order", label: "Byte Order", kind: "enum", options: BYTE_ORDER, minWidth: "min-w-[110px]" },
  { key: "word_order", label: "Word Order", kind: "enum", options: WORD_ORDER, minWidth: "min-w-[110px]" },
  { key: "class", label: "Class", kind: "enum", options: POINT_CLASS, minWidth: "min-w-[100px]" },
  { key: "severity", label: "Severity", kind: "enum", options: SEVERITY, minWidth: "min-w-[100px]" },
];

// Number cells accept only numeric (or empty) text; enum cells only their options.
function normalizeForColumn(column: Column, rawValue: string): string | null {
  const value = rawValue.trim();
  if (column.kind === "number") return value === "" || !Number.isNaN(Number(value)) ? value : null;
  if (column.kind === "enum") {
    if (value === "") return OPTIONAL_ENUM_COLUMNS.includes(column.key) ? "" : null;
    const match = (column.options ?? []).find(option => option.toLowerCase() === value.toLowerCase());
    return match ?? null;
  }
  return rawValue;
}

type RowValues = Record<ColumnKey, string>;

interface GridRow {
  id: number | null; // backend id; null for new (unsaved) rows
  values: RowValues;
}

const EMPTY_VALUES: RowValues = {
  name: "", category: "NATIVE", poll_kind: "holding", address: "", size: "1",
  data_type: "int16", unit: "", scale_factor: "1", byte_order: "big",
  word_order: "msw_first", class: "", severity: "",
};

function pointToValues(point: DevicePoint): RowValues {
  return {
    name: point.name ?? "",
    category: point.category,
    poll_kind: point.poll_kind ?? "",
    address: point.address != null ? String(point.address) : "",
    size: String(point.size),
    data_type: point.data_type ?? "",
    unit: point.unit ?? "",
    scale_factor: point.scale_factor != null ? String(point.scale_factor) : "",
    byte_order: point.byte_order || "big",
    word_order: point.word_order || "msw_first",
    class: point.class ?? "",
    severity: point.severity ?? "",
  };
}

// Non-editable cell: category is fixed once a point exists (backend does not update it).
function isCellEditable(row: GridRow, column: Column): boolean {
  if (column.key === "category" && row.id !== null) return false;
  return true;
}

interface SaveChanges {
  updates: { id: number; payload: DevicePointUpdateRequest }[];
  creates: DevicePointCreateRequest[];
}

interface CellPosition { rowIndex: number; columnIndex: number; }
interface Rect { startRow: number; startColumn: number; endRow: number; endColumn: number; }

function normalize(cellA: CellPosition, cellB: CellPosition): Rect {
  return {
    startRow: Math.min(cellA.rowIndex, cellB.rowIndex),
    endRow: Math.max(cellA.rowIndex, cellB.rowIndex),
    startColumn: Math.min(cellA.columnIndex, cellB.columnIndex),
    endColumn: Math.max(cellA.columnIndex, cellB.columnIndex),
  };
}

function inRect(rowIndex: number, columnIndex: number, rect: Rect | null): boolean {
  return !!rect
    && rowIndex >= rect.startRow && rowIndex <= rect.endRow
    && columnIndex >= rect.startColumn && columnIndex <= rect.endColumn;
}

export function DevicePointsGrid({ points, disabled, isSaving, onSave, onRequestDelete }: {
  points: DevicePoint[];
  disabled: boolean;
  isSaving: boolean;
  onSave: (changes: SaveChanges) => Promise<void>;
  onRequestDelete: (point: DevicePoint) => void;
}) {
  const baseline = useMemo<GridRow[]>(
    () => points.map(point => ({ id: point.id, values: pointToValues(point) })),
    [points],
  );
  // Signature so background refetches with identical data don't clobber in-progress edits.
  const signature = useMemo(
    () => baseline.map(row => `${row.id}:${JSON.stringify(row.values)}`).join("|") + `#${baseline.length}`,
    [baseline],
  );

  const [rows, setRows] = useState<GridRow[]>(baseline);
  const lastSignature = useRef(signature);
  useEffect(() => {
    if (lastSignature.current !== signature) {
      lastSignature.current = signature;
      setRows(baseline);
      setAnchor(null);
      setFocusCell(null);
      setEditing(null);
      setErrorCells(new Set());
    }
  }, [signature, baseline]);

  const baselineById = useMemo(() => {
    const byId = new Map<number, RowValues>();
    baseline.forEach(row => { if (row.id !== null) byId.set(row.id, row.values); });
    return byId;
  }, [baseline]);

  // ---- selection / editing state ----
  const [anchor, setAnchor] = useState<CellPosition | null>(null);
  const [focusCell, setFocusCell] = useState<CellPosition | null>(null);
  const [editing, setEditing] = useState<CellPosition | null>(null);
  const [errorCells, setErrorCells] = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const editRef = useRef<HTMLInputElement | HTMLSelectElement | null>(null);
  const editSnapshot = useRef<{ position: CellPosition; value: string } | null>(null);
  const clipboardFallback = useRef(""); // used when the async Clipboard API is unavailable

  const selection = anchor && focusCell ? normalize(anchor, focusCell) : null;
  const rowCount = rows.length;
  const columnCount = COLUMNS.length;

  // ---- per-column filters ----
  const emptyFilters = () => Object.fromEntries(COLUMNS.map(column => [column.key, ""])) as Record<ColumnKey, string>;
  const [filters, setFilters] = useState<Record<ColumnKey, string>>(emptyFilters);
  const filtersActive = COLUMNS.some(column => filters[column.key] !== "");

  const matchesFilters = useCallback((row: GridRow): boolean =>
    COLUMNS.every(column => {
      const filterValue = filters[column.key];
      if (filterValue === "") return true;
      const cell = row.values[column.key];
      if (column.kind === "enum") return cell === filterValue;
      return cell.toLowerCase().includes(filterValue.toLowerCase());
    }), [filters]);

  // Indices into `rows` that pass the filters, in order. Selection/edit still use real
  // row indices; range operations (fill/paste/copy/clear) skip rows not in this set.
  const visibleIndices = useMemo(
    () => rows.map((_, index) => index).filter(index => matchesFilters(rows[index])),
    [rows, matchesFilters],
  );
  const visibleInRange = (start: number, end: number) => visibleIndices.filter(index => index >= start && index <= end);

  const updateFilter = (key: ColumnKey, value: string) => {
    setFilters(previous => ({ ...previous, [key]: value }));
    setAnchor(null); setFocusCell(null); setEditing(null);
  };
  const clearFilters = () => setFilters(emptyFilters());
  const [addCount, setAddCount] = useState("1");

  const dragMode = useRef<null | "select" | "fill">(null);
  const fillBase = useRef<Rect | null>(null);

  // Focus the edit input whenever a cell enters edit mode (autoFocus alone is unreliable).
  useEffect(() => {
    if (editing && editRef.current) {
      editRef.current.focus();
      if (editRef.current instanceof HTMLInputElement) editRef.current.select();
    }
  }, [editing]);

  const setCell = useCallback((rowIndex: number, columnIndex: number, value: string) => {
    setRows(previous => {
      const column = COLUMNS[columnIndex];
      if (rowIndex < 0 || rowIndex >= previous.length || !isCellEditable(previous[rowIndex], column)) return previous;
      const next = previous.slice();
      next[rowIndex] = { ...next[rowIndex], values: { ...next[rowIndex].values, [column.key]: value } };
      return next;
    });
  }, []);

  const focusContainer = () => containerRef.current?.focus();

  // ---- editing ----
  const beginEdit = useCallback((position: CellPosition, replaceChar?: string) => {
    const column = COLUMNS[position.columnIndex];
    if (!isCellEditable(rows[position.rowIndex], column)) return;
    editSnapshot.current = { position, value: rows[position.rowIndex].values[column.key] };
    if (replaceChar !== undefined) setCell(position.rowIndex, position.columnIndex, replaceChar);
    setEditing(position);
  }, [rows, setCell]);

  const stopEdit = useCallback(() => {
    editSnapshot.current = null;
    setEditing(null);
  }, []);

  const cancelEdit = useCallback(() => {
    const snapshot = editSnapshot.current;
    if (snapshot) setCell(snapshot.position.rowIndex, snapshot.position.columnIndex, snapshot.value);
    editSnapshot.current = null;
    setEditing(null);
  }, [setCell]);

  // ---- mouse handlers ----
  const onCellMouseDown = (rowIndex: number, columnIndex: number, event: React.MouseEvent) => {
    if (editing) stopEdit();
    focusContainer();
    if (event.shiftKey && anchor) {
      setFocusCell({ rowIndex, columnIndex });
    } else {
      setAnchor({ rowIndex, columnIndex });
      setFocusCell({ rowIndex, columnIndex });
    }
    dragMode.current = "select";
  };

  const onCellMouseEnter = (rowIndex: number, columnIndex: number) => {
    if (dragMode.current === "select") {
      setFocusCell({ rowIndex, columnIndex });
    } else if (dragMode.current === "fill" && fillBase.current) {
      const baseRect = fillBase.current;
      const targetRow = Math.max(baseRect.endRow, rowIndex);
      setAnchor({ rowIndex: baseRect.startRow, columnIndex: baseRect.startColumn });
      setFocusCell({ rowIndex: targetRow, columnIndex: baseRect.endColumn });
    }
  };

  const onFillHandleMouseDown = (event: React.MouseEvent) => {
    event.stopPropagation();
    event.preventDefault();
    if (!selection) return;
    fillBase.current = { ...selection };
    dragMode.current = "fill";
  };

  const applyFill = useCallback((baseRect: Rect, fullRect: Rect) => {
    if (fullRect.endRow <= baseRect.endRow) return;
    const sourceRows = visibleIndices.filter(index => index >= baseRect.startRow && index <= baseRect.endRow);
    const targetRows = visibleIndices.filter(index => index > baseRect.endRow && index <= fullRect.endRow);
    if (sourceRows.length === 0) return;
    setRows(previous => {
      const next = previous.slice();
      targetRows.forEach((rowIndex, offset) => {
        const patternRow = sourceRows[offset % sourceRows.length];
        for (let columnIndex = baseRect.startColumn; columnIndex <= baseRect.endColumn; columnIndex++) {
          const column = COLUMNS[columnIndex];
          if (!isCellEditable(next[rowIndex], column)) continue;
          next[rowIndex] = { ...next[rowIndex], values: { ...next[rowIndex].values, [column.key]: previous[patternRow].values[column.key] } };
        }
      });
      return next;
    });
  }, [visibleIndices]);

  // Global mouseup: end any drag, and apply the fill if one was in progress.
  useEffect(() => {
    const handleMouseUp = () => {
      if (dragMode.current === "fill" && fillBase.current && selection) {
        applyFill(fillBase.current, selection);
      }
      dragMode.current = null;
      fillBase.current = null;
    };
    window.addEventListener("mouseup", handleMouseUp);
    return () => window.removeEventListener("mouseup", handleMouseUp);
  }, [selection, applyFill]);

  // ---- keyboard ----
  const moveActive = (deltaRow: number, deltaColumn: number, extend: boolean) => {
    const current = focusCell ?? anchor ?? { rowIndex: visibleIndices[0] ?? 0, columnIndex: 0 };
    let newRow = current.rowIndex;
    if (deltaRow !== 0 && visibleIndices.length > 0) {
      const position = visibleIndices.indexOf(current.rowIndex);
      if (position === -1) {
        newRow = visibleIndices[0];
      } else {
        newRow = visibleIndices[Math.min(Math.max(position + deltaRow, 0), visibleIndices.length - 1)];
      }
    }
    const newColumn = Math.min(Math.max(current.columnIndex + deltaColumn, 0), columnCount - 1);
    if (extend && anchor) {
      setFocusCell({ rowIndex: newRow, columnIndex: newColumn });
    } else {
      setAnchor({ rowIndex: newRow, columnIndex: newColumn });
      setFocusCell({ rowIndex: newRow, columnIndex: newColumn });
    }
  };

  const clearSelection = () => {
    if (!selection) return;
    const targetRows = visibleInRange(selection.startRow, selection.endRow);
    setRows(previous => {
      const next = previous.slice();
      for (const rowIndex of targetRows) {
        for (let columnIndex = selection.startColumn; columnIndex <= selection.endColumn; columnIndex++) {
          const column = COLUMNS[columnIndex];
          if (!isCellEditable(next[rowIndex], column)) continue;
          next[rowIndex] = { ...next[rowIndex], values: { ...next[rowIndex].values, [column.key]: "" } };
        }
      }
      return next;
    });
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (editing) {
      if (event.key === "Enter") { event.preventDefault(); stopEdit(); focusContainer(); moveActive(1, 0, false); }
      else if (event.key === "Escape") { event.preventDefault(); cancelEdit(); focusContainer(); }
      else if (event.key === "Tab") { event.preventDefault(); stopEdit(); focusContainer(); moveActive(0, event.shiftKey ? -1 : 1, false); }
      return;
    }
    // Ignore keys originating from the filter row controls (they handle their own input).
    const tagName = (event.target as HTMLElement).tagName;
    if (tagName === "INPUT" || tagName === "SELECT" || tagName === "TEXTAREA") return;
    const active = focusCell ?? anchor;
    if (event.ctrlKey || event.metaKey) {
      const key = event.key.toLowerCase();
      if (key === "c") { event.preventDefault(); copySelection(); return; }
      if (key === "x") { event.preventDefault(); copySelection(); clearSelection(); return; }
      if (key === "v") { event.preventDefault(); pasteFromClipboard(); return; }
      if (key === "z") { event.preventDefault(); if (dirtyCount > 0 && !isSaving) discard(); return; }
      if (key === "a") {
        event.preventDefault();
        setAnchor({ rowIndex: 0, columnIndex: 0 });
        setFocusCell({ rowIndex: rowCount - 1, columnIndex: columnCount - 1 });
        return;
      }
      return;
    }
    switch (event.key) {
      case "ArrowUp": event.preventDefault(); moveActive(-1, 0, event.shiftKey); break;
      case "ArrowDown": event.preventDefault(); moveActive(1, 0, event.shiftKey); break;
      case "ArrowLeft": event.preventDefault(); moveActive(0, -1, event.shiftKey); break;
      case "ArrowRight": event.preventDefault(); moveActive(0, 1, event.shiftKey); break;
      case "Tab": event.preventDefault(); moveActive(0, event.shiftKey ? -1 : 1, false); break;
      case "Enter": if (active) { event.preventDefault(); beginEdit(active); } break;
      case "F2": if (active) { event.preventDefault(); beginEdit(active); } break;
      case "Delete":
      case "Backspace": event.preventDefault(); clearSelection(); break;
      default:
        if (active && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          event.preventDefault();
          const column = COLUMNS[active.columnIndex];
          if (column.kind === "enum") beginEdit(active); // open dropdown, don't type into it
          else if (column.kind === "number") beginEdit(active, /[-+.\d]/.test(event.key) ? event.key : "");
          else beginEdit(active, event.key);
        }
    }
  };

  // ---- clipboard (Clipboard API — reliable on a focused div where copy/paste events are not) ----
  const copySelection = async () => {
    const selectionRect = selection;
    if (!selectionRect) return;
    const lines = visibleInRange(selectionRect.startRow, selectionRect.endRow).map(rowIndex => {
      const cells: string[] = [];
      for (let columnIndex = selectionRect.startColumn; columnIndex <= selectionRect.endColumn; columnIndex++) {
        cells.push(rows[rowIndex].values[COLUMNS[columnIndex].key]);
      }
      return cells.join("\t");
    });
    const tsv = lines.join("\n");
    try {
      await navigator.clipboard.writeText(tsv);
    } catch {
      clipboardFallback.current = tsv; // insecure context / API blocked
    }
  };

  const applyPasteText = (text: string) => {
    const active = focusCell ?? anchor;
    if (!active) return;
    const matrix = text.replace(/\r/g, "").replace(/\n$/, "").split("\n").map(line => line.split("\t"));
    const sourceRowCount = matrix.length;
    const sourceColumnCount = Math.max(...matrix.map(line => line.length));
    if (sourceRowCount === 0) return;

    // Target rows are always visible rows only. If a multi-cell range is selected, tile the
    // source across it (Excel behavior); otherwise paste starting at the active cell.
    const selectionRect = selection;
    const isMultiCell = selectionRect
      && (selectionRect.endRow - selectionRect.startRow + 1) * (selectionRect.endColumn - selectionRect.startColumn + 1) > 1;
    let targetRows: number[];
    let startColumn: number, endColumn: number;
    if (isMultiCell) {
      targetRows = visibleInRange(selectionRect!.startRow, selectionRect!.endRow);
      startColumn = selectionRect!.startColumn;
      endColumn = selectionRect!.endColumn;
    } else {
      const startPosition = visibleIndices.indexOf(active.rowIndex);
      const from = startPosition === -1 ? 0 : startPosition;
      targetRows = visibleIndices.slice(from, from + sourceRowCount);
      startColumn = active.columnIndex;
      endColumn = Math.min(active.columnIndex + sourceColumnCount - 1, columnCount - 1);
    }
    if (targetRows.length === 0) return;

    setRows(previous => {
      const next = previous.slice();
      targetRows.forEach((rowIndex, rowOffset) => {
        const sourceLine = matrix[rowOffset % sourceRowCount];
        for (let columnIndex = startColumn; columnIndex <= endColumn && columnIndex < columnCount; columnIndex++) {
          const column = COLUMNS[columnIndex];
          if (!isCellEditable(next[rowIndex], column)) continue;
          const rawValue = sourceLine[(columnIndex - startColumn) % sourceLine.length] ?? "";
          const normalized = normalizeForColumn(column, rawValue);
          if (normalized === null) continue; // reject values that don't fit the column type
          next[rowIndex] = { ...next[rowIndex], values: { ...next[rowIndex].values, [column.key]: normalized } };
        }
      });
      return next;
    });
    setAnchor({ rowIndex: targetRows[0], columnIndex: startColumn });
    setFocusCell({ rowIndex: targetRows[targetRows.length - 1], columnIndex: endColumn });
  };

  const pasteFromClipboard = async () => {
    let text = "";
    try {
      text = await navigator.clipboard.readText();
    } catch {
      text = clipboardFallback.current; // insecure context / API blocked
    }
    if (text) applyPasteText(text);
  };

  // ---- rows management ----
  const addRows = () => {
    const count = Math.min(Math.max(Math.floor(Number(addCount) || 1), 1), 1000);
    if (filtersActive) setFilters(emptyFilters()); // ensure the new rows are visible
    const newIndex = rows.length;
    setRows(previous => [
      ...previous,
      ...Array.from({ length: count }, () => ({ id: null as number | null, values: { ...EMPTY_VALUES } })),
    ]);
    setAnchor({ rowIndex: newIndex, columnIndex: 0 });
    setFocusCell({ rowIndex: newIndex, columnIndex: 0 });
  };

  const deleteRow = (rowIndex: number) => {
    const row = rows[rowIndex];
    if (row.id === null) {
      setRows(previous => previous.filter((_, index) => index !== rowIndex));
      setAnchor(null); setFocusCell(null); setEditing(null);
    } else {
      const point = points.find(candidate => candidate.id === row.id);
      if (point) onRequestDelete(point);
    }
  };

  const discard = () => {
    setRows(baseline);
    setAnchor(null); setFocusCell(null); setEditing(null);
    setErrorCells(new Set());
  };

  // ---- dirty + validation ----
  const isRowDirty = (row: GridRow): boolean => {
    const base = row.id === null ? EMPTY_VALUES : baselineById.get(row.id);
    if (!base) return true;
    return COLUMNS.some(column => row.values[column.key] !== base[column.key]);
  };

  const dirtyCount = rows.filter(isRowDirty).length;

  const validateAndBuild = (): { changes: SaveChanges | null; errors: Set<string> } => {
    const errors = new Set<string>();
    const updates: SaveChanges["updates"] = [];
    const creates: DevicePointCreateRequest[] = [];

    rows.forEach((row, rowIndex) => {
      if (!isRowDirty(row)) return;
      const values = row.values;
      const addError = (columnIndex: number) => errors.add(`${rowIndex}:${columnIndex}`);

      if (values.name.trim() === "") addError(0);
      const size = Number(values.size);
      if (values.size.trim() === "" || !Number.isInteger(size) || size < 1) addError(4);
      if (!(DATA_TYPE as string[]).includes(values.data_type)) addError(5);
      if (values.address.trim() !== "") {
        const addressValue = Number(values.address);
        if (!Number.isInteger(addressValue) || addressValue < 0 || addressValue > 65535) addError(3);
      }
      if (values.scale_factor.trim() !== "" && Number.isNaN(Number(values.scale_factor))) addError(7);
      if (!CATEGORY.includes(values.category)) addError(1);
      if (values.poll_kind !== "" && !POLL_KIND.includes(values.poll_kind)) addError(2);
      if (!BYTE_ORDER.includes(values.byte_order)) addError(8);
      if (!WORD_ORDER.includes(values.word_order)) addError(9);
      if (values.class !== "" && !(POINT_CLASS as string[]).includes(values.class)) addError(10);
      if (values.severity !== "" && !(SEVERITY as string[]).includes(values.severity)) addError(11);

      const rowHasError = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11].some(columnIndex => errors.has(`${rowIndex}:${columnIndex}`));
      if (rowHasError) return;

      const payload: DevicePointUpdateRequest = {
        name: values.name.trim(),
        size,
        data_type: values.data_type.trim() as DevicePointDataType,
        byte_order: values.byte_order,
        word_order: values.word_order,
        poll_kind: values.poll_kind !== "" ? (values.poll_kind as "holding" | "input" | "coils") : null,
        address: values.address.trim() !== "" ? Number(values.address) : null,
        unit: values.unit.trim() !== "" ? values.unit.trim() : null,
        scale_factor: values.scale_factor.trim() !== "" ? Number(values.scale_factor) : null,
        class: values.class !== "" ? (values.class as DevicePointClass) : null,
        severity: values.severity !== "" ? (values.severity as DevicePointSeverity) : null,
      };

      if (row.id === null) {
        creates.push({ ...payload, category: values.category as DevicePointCreateRequest["category"] } as DevicePointCreateRequest);
      } else {
        updates.push({ id: row.id, payload });
      }
    });

    if (errors.size > 0) return { changes: null, errors };
    return { changes: { updates, creates }, errors };
  };

  const handleSave = async () => {
    if (editing) stopEdit();
    const { changes, errors } = validateAndBuild();
    setErrorCells(errors);
    if (!changes) return;
    if (changes.updates.length === 0 && changes.creates.length === 0) return;
    await onSave(changes);
  };

  // ---- render ----
  const activeCell = focusCell ?? anchor;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Click a cell and type to edit. Drag to select, Ctrl+C / Ctrl+V to copy-paste, drag the corner handle to fill down. Use the filter row to narrow points.
        </p>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            max={1000}
            value={addCount}
            onChange={(event) => setAddCount(event.target.value)}
            disabled={disabled}
            title="Number of rows to add"
            className="h-9 w-16 rounded-md border border-input bg-background px-2 text-sm disabled:opacity-50"
          />
          <Button variant="outline" size="sm" className="gap-1" disabled={disabled} onClick={addRows}>
            <Plus className="w-4 h-4" />Add Row{(Number(addCount) || 1) > 1 ? "s" : ""}
          </Button>
          <Button variant="ghost" size="sm" className="gap-1" disabled={dirtyCount === 0 || isSaving} onClick={discard}>
            <Undo2 className="w-4 h-4" />Discard
          </Button>
          <Button size="sm" className="gap-1" disabled={disabled || dirtyCount === 0 || isSaving} onClick={handleSave}>
            <Save className="w-4 h-4" />{isSaving ? "Saving..." : `Save${dirtyCount ? ` (${dirtyCount})` : ""}`}
          </Button>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="text-muted-foreground py-12 text-center">No points yet. Click "Add Row" to create one.</p>
      ) : (
        <div
          ref={containerRef}
          tabIndex={0}
          onKeyDown={onKeyDown}
          className="overflow-x-auto rounded-md border border-border outline-none"
        >
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-muted/50">
                <th className="sticky left-0 z-10 bg-muted/50 border-b border-r border-border px-2 py-1.5 text-left text-xs font-medium text-muted-foreground w-10">#</th>
                {COLUMNS.map(column => (
                  <th key={column.key} className={cn("border-b border-r border-border px-2 py-1.5 text-left text-xs font-medium text-muted-foreground", column.minWidth)}>
                    {column.label}
                  </th>
                ))}
                <th className="border-b border-border px-2 py-1.5 w-10" />
              </tr>
              <tr className="bg-background">
                <th className="sticky left-0 z-10 bg-background border-b border-r border-border px-1 py-1" />
                {COLUMNS.map(column => (
                  <th key={column.key} className="border-b border-r border-border px-1 py-1 align-top">
                    {column.kind === "enum" ? (
                      <select
                        value={filters[column.key]}
                        onChange={(event) => updateFilter(column.key, event.target.value)}
                        className="w-full h-7 rounded border border-input bg-background px-1 text-xs font-normal"
                      >
                        <option value="">All</option>
                        {(column.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}
                      </select>
                    ) : (
                      <input
                        value={filters[column.key]}
                        onChange={(event) => updateFilter(column.key, event.target.value)}
                        placeholder="Filter…"
                        className="w-full h-7 rounded border border-input bg-background px-1.5 text-xs font-normal"
                      />
                    )}
                  </th>
                ))}
                <th className="border-b border-border px-1 py-1 text-center">
                  {filtersActive && (
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={clearFilters} title="Clear filters">
                      <X className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleIndices.length === 0 && (
                <tr>
                  <td colSpan={columnCount + 2} className="text-muted-foreground py-8 text-center text-sm">
                    No points match the filters.
                  </td>
                </tr>
              )}
              {visibleIndices.map((rowIndex) => {
                const row = rows[rowIndex];
                const dirty = isRowDirty(row);
                return (
                  <tr key={row.id ?? `new-${rowIndex}`}>
                    <td className={cn(
                      "sticky left-0 z-10 border-b border-r border-border px-2 py-1 text-xs text-muted-foreground tabular-nums bg-background",
                      dirty && "text-primary font-medium",
                    )}>
                      {row.id === null ? "＋" : rowIndex + 1}
                    </td>
                    {COLUMNS.map((column, columnIndex) => {
                      const isEditing = editing?.rowIndex === rowIndex && editing?.columnIndex === columnIndex;
                      const isActive = activeCell?.rowIndex === rowIndex && activeCell?.columnIndex === columnIndex;
                      const selected = inRect(rowIndex, columnIndex, selection);
                      const editable = isCellEditable(row, column);
                      const isFillCorner = selection && rowIndex === selection.endRow && columnIndex === selection.endColumn && !isEditing;
                      const hasError = errorCells.has(`${rowIndex}:${columnIndex}`);
                      const cellValue = row.values[column.key];
                      return (
                        <td
                          key={column.key}
                          onMouseDown={(event) => { if (editable && !isEditing) onCellMouseDown(rowIndex, columnIndex, event); }}
                          onMouseEnter={() => onCellMouseEnter(rowIndex, columnIndex)}
                          onDoubleClick={() => editable && beginEdit({ rowIndex, columnIndex })}
                          className={cn(
                            "relative border-b border-r border-border px-2 py-1 h-8",
                            editable ? "cursor-cell" : "cursor-not-allowed bg-muted/30 text-muted-foreground",
                            !isEditing && "select-none",
                            selected && !isEditing && "bg-primary/10",
                            isActive && !isEditing && "ring-1 ring-inset ring-primary",
                            hasError && "bg-destructive/15 ring-1 ring-inset ring-destructive",
                          )}
                        >
                          {isEditing ? (
                            column.kind === "enum" ? (
                              <select
                                ref={(element) => { editRef.current = element; }}
                                value={cellValue}
                                onChange={(event) => setCell(rowIndex, columnIndex, event.target.value)}
                                onBlur={stopEdit}
                                className="absolute inset-0 w-full h-full bg-background px-2 text-sm outline-none ring-1 ring-inset ring-primary"
                              >
                                {!(column.options ?? []).includes(cellValue) && <option value={cellValue}>{cellValue === "" ? "—" : cellValue}</option>}
                                {(column.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}
                              </select>
                            ) : (
                              <input
                                ref={(element) => { editRef.current = element; }}
                                type={column.kind === "number" ? "number" : "text"}
                                inputMode={column.kind === "number" ? "decimal" : "text"}
                                step={column.kind === "number" ? (column.key === "scale_factor" ? "any" : "1") : undefined}
                                value={cellValue}
                                onChange={(event) => setCell(rowIndex, columnIndex, event.target.value)}
                                onBlur={stopEdit}
                                className="absolute inset-0 w-full h-full bg-background px-2 text-sm outline-none ring-1 ring-inset ring-primary"
                              />
                            )
                          ) : (
                            <span className="block truncate">
                              {OPTIONAL_ENUM_COLUMNS.includes(column.key) && cellValue === "" ? "—" : cellValue}
                            </span>
                          )}
                          {isFillCorner && (
                            <div
                              onMouseDown={onFillHandleMouseDown}
                              className="absolute -bottom-[3px] -right-[3px] w-2 h-2 bg-primary border border-background cursor-crosshair z-20"
                            />
                          )}
                        </td>
                      );
                    })}
                    <td className="border-b border-border px-1 py-1 text-center">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteRow(rowIndex)}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {errorCells.size > 0 && (
        <p className="text-xs text-destructive">
          {errorCells.size} invalid cell{errorCells.size > 1 ? "s" : ""} highlighted. Fix them before saving (Name &amp; Data Type required, Size ≥ 1, Address 0–65535).
        </p>
      )}
    </div>
  );
}
