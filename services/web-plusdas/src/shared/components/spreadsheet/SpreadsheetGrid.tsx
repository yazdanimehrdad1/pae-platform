import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { cellKey, newRowKey, normalizeForColumn, type GridColumn, type GridRow } from "./grid";

export type { GridColumn, GridColumnKind, GridRow } from "./grid";

// A spreadsheet-style table: cell selection, keyboard navigation, typing to edit, TSV
// copy/paste, fill-down handle, a filter row and "add N rows". It is controlled — the parent
// owns `rows` and gets every change through `onRowsChange` — and knows nothing about what the
// rows mean: validation, dirty tracking and saving stay with the parent.

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

const EDITABLE_HINT =
  "Click a cell and type to edit. Drag to select, Ctrl+C / Ctrl+V to copy-paste, drag the corner handle to fill down. Use the filter row to narrow rows.";
const READ_ONLY_HINT = "Drag to select, Ctrl+C to copy. Use the filter row to narrow rows.";

export interface SpreadsheetGridProps<K extends string> {
  columns: GridColumn<K>[];
  rows: GridRow<K>[];
  onRowsChange?: (rows: GridRow<K>[]) => void;
  /** Values a row added with "Add Row" starts with. */
  newRowValues?: Record<K, string>;
  /** Selection, copy and filters only: no typing, paste, fill, add or delete. */
  readOnly?: boolean;
  /** Disables "Add Row". */
  disabled?: boolean;
  isCellEditable?: (row: GridRow<K>, column: GridColumn<K>) => boolean;
  /** Cells to highlight as invalid, keyed with `cellKey(rowIndex, columnKey)`. */
  errorCells?: Set<string>;
  isRowDirty?: (row: GridRow<K>) => boolean;
  /** New rows show "＋" instead of their number. */
  isRowNew?: (row: GridRow<K>) => boolean;
  /** Adds a delete column with a button per row (not in read-only mode); without it there is no such column. */
  onDeleteRow?: (rowIndex: number) => void;
  /** Ctrl+Z: throw away every unsaved change. */
  onDiscardAll?: () => void;
  /** Change it to drop the selection and any in-progress edit (e.g. after a reset). */
  resetToken?: number | string;
  /** Extra buttons, right of "Add Row". */
  toolbar?: ReactNode;
  hint?: string;
  emptyMessage?: string;
  noMatchMessage?: string;
}

export function SpreadsheetGrid<K extends string>({
  columns, rows, onRowsChange, newRowValues, readOnly = false, disabled = false,
  isCellEditable, errorCells, isRowDirty, isRowNew, onDeleteRow, onDiscardAll, resetToken,
  toolbar, hint, emptyMessage = "No rows yet.", noMatchMessage = "No rows match the filters.",
}: SpreadsheetGridProps<K>) {
  const canEdit = useCallback(
    (row: GridRow<K>, column: GridColumn<K>) => !readOnly && (isCellEditable ? isCellEditable(row, column) : true),
    [readOnly, isCellEditable],
  );

  // Latest rows, also between renders: several edits in one event build on each other.
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const updateRows = useCallback((updater: (previous: GridRow<K>[]) => GridRow<K>[]) => {
    const next = updater(rowsRef.current);
    if (next === rowsRef.current) return;
    rowsRef.current = next;
    onRowsChange?.(next);
  }, [onRowsChange]);

  // ---- selection / editing state ----
  const [anchor, setAnchor] = useState<CellPosition | null>(null);
  const [focusCell, setFocusCell] = useState<CellPosition | null>(null);
  const [editing, setEditing] = useState<CellPosition | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const editRef = useRef<HTMLInputElement | HTMLSelectElement | null>(null);
  const editSnapshot = useRef<{ position: CellPosition; value: string } | null>(null);
  const clipboardFallback = useRef(""); // used when the async Clipboard API is unavailable

  const clearSelectionState = () => { setAnchor(null); setFocusCell(null); setEditing(null); };

  const lastResetToken = useRef(resetToken);
  useEffect(() => {
    if (lastResetToken.current !== resetToken) {
      lastResetToken.current = resetToken;
      clearSelectionState();
    }
  }, [resetToken]);

  const rowCount = rows.length;
  const columnCount = columns.length;

  // Rows can shrink under the selection (a delete, a refetch, a live update): drop it then.
  useEffect(() => {
    const outOfRange = (position: CellPosition | null) => !!position && position.rowIndex >= rowCount;
    if (outOfRange(anchor) || outOfRange(focusCell) || outOfRange(editing)) clearSelectionState();
  }, [rowCount, anchor, focusCell, editing]);

  const selection = anchor && focusCell ? normalize(anchor, focusCell) : null;

  // ---- per-column filters ----
  const emptyFilters = useCallback(
    () => Object.fromEntries(columns.map(column => [column.key, ""])) as Record<K, string>,
    [columns],
  );
  const [filters, setFilters] = useState<Record<K, string>>(emptyFilters);
  const filtersActive = columns.some(column => (filters[column.key] ?? "") !== "");

  const matchesFilters = useCallback((row: GridRow<K>): boolean =>
    columns.every(column => {
      const filterValue = filters[column.key] ?? "";
      if (filterValue === "") return true;
      const cell = row.values[column.key] ?? "";
      if (column.kind === "enum") return cell === filterValue;
      return cell.toLowerCase().includes(filterValue.toLowerCase());
    }), [columns, filters]);

  // Indices into `rows` that pass the filters, in order. Selection/edit still use real
  // row indices; range operations (fill/paste/copy/clear) skip rows not in this set.
  const visibleIndices = useMemo(
    () => rows.map((_, index) => index).filter(index => matchesFilters(rows[index])),
    [rows, matchesFilters],
  );
  const visibleInRange = (start: number, end: number) => visibleIndices.filter(index => index >= start && index <= end);

  const updateFilter = (key: K, value: string) => {
    setFilters(previous => ({ ...previous, [key]: value }));
    clearSelectionState();
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
    updateRows(previous => {
      const column = columns[columnIndex];
      if (rowIndex < 0 || rowIndex >= previous.length || !canEdit(previous[rowIndex], column)) return previous;
      const next = previous.slice();
      next[rowIndex] = { ...next[rowIndex], values: { ...next[rowIndex].values, [column.key]: value } };
      return next;
    });
  }, [updateRows, columns, canEdit]);

  const focusContainer = () => containerRef.current?.focus();

  // ---- editing ----
  const beginEdit = useCallback((position: CellPosition, replaceChar?: string) => {
    const column = columns[position.columnIndex];
    const row = rowsRef.current[position.rowIndex];
    if (!row || !canEdit(row, column)) return;
    editSnapshot.current = { position, value: row.values[column.key] };
    if (replaceChar !== undefined) setCell(position.rowIndex, position.columnIndex, replaceChar);
    setEditing(position);
  }, [columns, canEdit, setCell]);

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
    updateRows(previous => {
      const next = previous.slice();
      targetRows.forEach((rowIndex, offset) => {
        const patternRow = sourceRows[offset % sourceRows.length];
        for (let columnIndex = baseRect.startColumn; columnIndex <= baseRect.endColumn; columnIndex++) {
          const column = columns[columnIndex];
          if (!canEdit(next[rowIndex], column)) continue;
          next[rowIndex] = { ...next[rowIndex], values: { ...next[rowIndex].values, [column.key]: previous[patternRow].values[column.key] } };
        }
      });
      return next;
    });
  }, [visibleIndices, updateRows, columns, canEdit]);

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

  const clearSelectedCells = () => {
    if (!selection || readOnly) return;
    const targetRows = visibleInRange(selection.startRow, selection.endRow);
    updateRows(previous => {
      const next = previous.slice();
      for (const rowIndex of targetRows) {
        for (let columnIndex = selection.startColumn; columnIndex <= selection.endColumn; columnIndex++) {
          const column = columns[columnIndex];
          if (!canEdit(next[rowIndex], column)) continue;
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
      if (key === "x") { event.preventDefault(); copySelection(); clearSelectedCells(); return; }
      if (key === "v") { event.preventDefault(); if (!readOnly) pasteFromClipboard(); return; }
      if (key === "z") { event.preventDefault(); if (!readOnly) onDiscardAll?.(); return; }
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
      case "Backspace": event.preventDefault(); clearSelectedCells(); break;
      default:
        if (active && !readOnly && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          event.preventDefault();
          const column = columns[active.columnIndex];
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
        cells.push(rows[rowIndex].values[columns[columnIndex].key]);
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
    if (!active || readOnly) return;
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

    updateRows(previous => {
      const next = previous.slice();
      targetRows.forEach((rowIndex, rowOffset) => {
        const sourceLine = matrix[rowOffset % sourceRowCount];
        for (let columnIndex = startColumn; columnIndex <= endColumn && columnIndex < columnCount; columnIndex++) {
          const column = columns[columnIndex];
          if (!canEdit(next[rowIndex], column)) continue;
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
    if (readOnly || disabled || !newRowValues) return;
    const count = Math.min(Math.max(Math.floor(Number(addCount) || 1), 1), 1000);
    if (filtersActive) setFilters(emptyFilters()); // ensure the new rows are visible
    const newIndex = rows.length;
    updateRows(previous => [
      ...previous,
      ...Array.from({ length: count }, () => ({ key: newRowKey(), values: { ...newRowValues } })),
    ]);
    setAnchor({ rowIndex: newIndex, columnIndex: 0 });
    setFocusCell({ rowIndex: newIndex, columnIndex: 0 });
  };

  const deleteRow = (rowIndex: number) => {
    clearSelectionState();
    onDeleteRow?.(rowIndex);
  };

  // ---- render ----
  const activeCell = focusCell ?? anchor;
  const showDeleteColumn = !readOnly && !!onDeleteRow;
  const canAddRows = !readOnly && !!newRowValues;
  const hintText = hint ?? (readOnly ? READ_ONLY_HINT : EDITABLE_HINT);
  const alignClass = (column: GridColumn<K>) => column.align === "right" && "text-right tabular-nums";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">{hintText}</p>
        {(canAddRows || toolbar) && (
          <div className="flex items-center gap-2">
            {canAddRows && (
              <>
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={addCount}
                  onChange={(event) => setAddCount(event.target.value)}
                  onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addRows(); } }}
                  disabled={disabled}
                  title="Number of rows to add"
                  className="h-9 w-16 rounded-md border border-input bg-background px-2 text-sm disabled:opacity-50"
                />
                <Button type="button" variant="outline" size="sm" className="gap-1" disabled={disabled} onClick={addRows}>
                  <Plus className="w-4 h-4" />Add Row{(Number(addCount) || 1) > 1 ? "s" : ""}
                </Button>
              </>
            )}
            {toolbar}
          </div>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="text-muted-foreground py-12 text-center">{emptyMessage}</p>
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
                {columns.map(column => (
                  <th key={column.key} className={cn("border-b border-r border-border px-2 py-1.5 text-left text-xs font-medium text-muted-foreground", column.minWidth, alignClass(column))}>
                    {column.label}
                  </th>
                ))}
                {showDeleteColumn && <th className="border-b border-border px-2 py-1.5 w-10" />}
              </tr>
              <tr className="bg-background">
                <th className="sticky left-0 z-10 bg-background border-b border-r border-border px-1 py-1 text-center">
                  {!showDeleteColumn && filtersActive && (
                    <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={clearFilters} title="Clear filters">
                      <X className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </th>
                {columns.map(column => (
                  <th key={column.key} className="border-b border-r border-border px-1 py-1 align-top">
                    {column.kind === "enum" ? (
                      <select
                        aria-label={`Filter ${column.label}`}
                        value={filters[column.key] ?? ""}
                        onChange={(event) => updateFilter(column.key, event.target.value)}
                        className="w-full h-7 rounded border border-input bg-background px-1 text-xs font-normal"
                      >
                        <option value="">All</option>
                        {(column.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}
                      </select>
                    ) : (
                      <input
                        aria-label={`Filter ${column.label}`}
                        value={filters[column.key] ?? ""}
                        onChange={(event) => updateFilter(column.key, event.target.value)}
                        onKeyDown={(event) => { if (event.key === "Enter") event.preventDefault(); }}
                        placeholder="Filter…"
                        className="w-full h-7 rounded border border-input bg-background px-1.5 text-xs font-normal"
                      />
                    )}
                  </th>
                ))}
                {showDeleteColumn && (
                  <th className="border-b border-border px-1 py-1 text-center">
                    {filtersActive && (
                      <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={clearFilters} title="Clear filters">
                        <X className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {visibleIndices.length === 0 && (
                <tr>
                  <td colSpan={columnCount + (showDeleteColumn ? 2 : 1)} className="text-muted-foreground py-8 text-center text-sm">
                    {noMatchMessage}
                  </td>
                </tr>
              )}
              {visibleIndices.map((rowIndex) => {
                const row = rows[rowIndex];
                const dirty = isRowDirty?.(row) ?? false;
                return (
                  <tr key={row.key}>
                    <td className={cn(
                      "sticky left-0 z-10 border-b border-r border-border px-2 py-1 text-xs text-muted-foreground tabular-nums bg-background",
                      dirty && "text-primary font-medium",
                    )}>
                      {isRowNew?.(row) ? "＋" : rowIndex + 1}
                    </td>
                    {columns.map((column, columnIndex) => {
                      const isEditing = editing?.rowIndex === rowIndex && editing?.columnIndex === columnIndex;
                      const isActive = activeCell?.rowIndex === rowIndex && activeCell?.columnIndex === columnIndex;
                      const selected = inRect(rowIndex, columnIndex, selection);
                      const editable = canEdit(row, column);
                      const selectable = editable || readOnly;
                      const isFillCorner = !readOnly && selection && rowIndex === selection.endRow && columnIndex === selection.endColumn && !isEditing;
                      const hasError = errorCells?.has(cellKey(rowIndex, column.key)) ?? false;
                      const cellValue = row.values[column.key] ?? "";
                      const emptyLabel = column.emptyLabel ?? "—";
                      return (
                        <td
                          key={column.key}
                          data-cell={cellKey(rowIndex, column.key)}
                          onMouseDown={(event) => { if (selectable && !isEditing) onCellMouseDown(rowIndex, columnIndex, event); }}
                          onMouseEnter={() => onCellMouseEnter(rowIndex, columnIndex)}
                          onDoubleClick={() => editable && beginEdit({ rowIndex, columnIndex })}
                          className={cn(
                            "relative border-b border-r border-border px-2 py-1 h-8",
                            selectable ? "cursor-cell" : "cursor-not-allowed bg-muted/30 text-muted-foreground",
                            !isEditing && "select-none",
                            selected && !isEditing && "bg-primary/10",
                            isActive && !isEditing && "ring-1 ring-inset ring-primary",
                            hasError && "bg-destructive/15 ring-1 ring-inset ring-destructive",
                            alignClass(column),
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
                                {column.optional && <option value="">{emptyLabel}</option>}
                                {!column.optional && !(column.options ?? []).includes(cellValue) && (
                                  <option value={cellValue}>{cellValue === "" ? emptyLabel : cellValue}</option>
                                )}
                                {(column.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}
                              </select>
                            ) : (
                              <input
                                ref={(element) => { editRef.current = element; }}
                                type={column.kind === "number" ? "number" : "text"}
                                inputMode={column.kind === "number" ? "decimal" : "text"}
                                step={column.kind === "number" ? (column.step ?? "1") : undefined}
                                value={cellValue}
                                onChange={(event) => setCell(rowIndex, columnIndex, event.target.value)}
                                onBlur={stopEdit}
                                className="absolute inset-0 w-full h-full bg-background px-2 text-sm outline-none ring-1 ring-inset ring-primary"
                              />
                            )
                          ) : (
                            <span className="block truncate">
                              {cellValue === "" && (column.optional || readOnly) ? emptyLabel : cellValue}
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
                    {showDeleteColumn && (
                      <td className="border-b border-border px-1 py-1 text-center">
                        <Button type="button" variant="ghost" size="icon" className="h-7 w-7" title="Delete row" onClick={() => deleteRow(rowIndex)}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
