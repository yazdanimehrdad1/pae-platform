import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Save, Undo2 } from "lucide-react";
import { cellKey, type GridColumn, type GridRow } from "@/shared/components/spreadsheet/grid";
import { SpreadsheetGrid } from "@/shared/components/spreadsheet/SpreadsheetGrid";
import type {
  DevicePoint, DevicePointClass, DevicePointCreateRequest, DevicePointDataType, DevicePointSeverity,
  DevicePointUpdateRequest,
} from "@/shared/types/device-point";

type ColumnKey =
  | "name" | "category" | "poll_kind" | "address" | "size" | "data_type"
  | "unit" | "scale_factor" | "byte_order" | "word_order" | "class" | "severity";

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
const BYTE_ORDER = ["big", "little"];
const WORD_ORDER = ["msw_first", "lsw_first"];

const COLUMNS: GridColumn<ColumnKey>[] = [
  { key: "name", label: "Name", kind: "text", minWidth: "min-w-[150px]" },
  { key: "category", label: "Category", kind: "enum", options: CATEGORY, minWidth: "min-w-[130px]" },
  { key: "poll_kind", label: "Poll Kind", kind: "enum", options: POLL_KIND, optional: true, minWidth: "min-w-[110px]" },
  { key: "address", label: "Address", kind: "number", minWidth: "min-w-[90px]" },
  { key: "size", label: "Size", kind: "number", minWidth: "min-w-[70px]" },
  { key: "data_type", label: "Data Type", kind: "enum", options: DATA_TYPE, minWidth: "min-w-[110px]" },
  { key: "unit", label: "Unit", kind: "text", minWidth: "min-w-[80px]" },
  { key: "scale_factor", label: "Scale", kind: "number", step: "any", minWidth: "min-w-[80px]" },
  { key: "byte_order", label: "Byte Order", kind: "enum", options: BYTE_ORDER, minWidth: "min-w-[110px]" },
  { key: "word_order", label: "Word Order", kind: "enum", options: WORD_ORDER, minWidth: "min-w-[110px]" },
  { key: "class", label: "Class", kind: "enum", options: POINT_CLASS, optional: true, minWidth: "min-w-[100px]" },
  { key: "severity", label: "Severity", kind: "enum", options: SEVERITY, optional: true, minWidth: "min-w-[100px]" },
];

type RowValues = Record<ColumnKey, string>;
type PointRow = GridRow<ColumnKey>;

const EMPTY_VALUES: RowValues = {
  name: "", category: "NATIVE", poll_kind: "holding", address: "", size: "1",
  data_type: "int16", unit: "", scale_factor: "1", byte_order: "big",
  word_order: "msw_first", class: "", severity: "",
};

const pointRowKey = (id: number) => `point-${id}`;

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

export interface SaveChanges {
  updates: { id: number; payload: DevicePointUpdateRequest }[];
  creates: DevicePointCreateRequest[];
}

export function DevicePointsGrid({ points, disabled, isSaving, onSave, onRequestDelete }: {
  points: DevicePoint[];
  disabled: boolean;
  isSaving: boolean;
  onSave: (changes: SaveChanges) => Promise<void>;
  onRequestDelete: (point: DevicePoint) => void;
}) {
  const baseline = useMemo<PointRow[]>(
    () => points.map(point => ({ key: pointRowKey(point.id), values: pointToValues(point) })),
    [points],
  );
  // Signature so background refetches with identical data don't clobber in-progress edits.
  const signature = useMemo(
    () => baseline.map(row => `${row.key}:${JSON.stringify(row.values)}`).join("|") + `#${baseline.length}`,
    [baseline],
  );

  const [rows, setRows] = useState<PointRow[]>(baseline);
  const [errorCells, setErrorCells] = useState<Set<string>>(new Set());
  const [resetToken, setResetToken] = useState(0);
  const lastSignature = useRef(signature);
  useEffect(() => {
    if (lastSignature.current !== signature) {
      lastSignature.current = signature;
      setRows(baseline);
      setErrorCells(new Set());
      setResetToken(token => token + 1);
    }
  }, [signature, baseline]);

  const baselineByKey = useMemo(() => new Map(baseline.map(row => [row.key, row.values])), [baseline]);
  const pointByKey = useMemo(() => new Map(points.map(point => [pointRowKey(point.id), point])), [points]);

  const isRowNew = (row: PointRow) => !baselineByKey.has(row.key);

  // Category is fixed once a point exists (backend does not update it).
  const isCellEditable = (row: PointRow, column: GridColumn<ColumnKey>) =>
    !(column.key === "category" && !isRowNew(row));

  const isRowDirty = (row: PointRow): boolean => {
    const base = baselineByKey.get(row.key) ?? EMPTY_VALUES;
    return COLUMNS.some(column => row.values[column.key] !== base[column.key]);
  };
  const dirtyCount = rows.filter(isRowDirty).length;

  const discard = () => {
    setRows(baseline);
    setErrorCells(new Set());
    setResetToken(token => token + 1);
  };

  const deleteRow = (rowIndex: number) => {
    const row = rows[rowIndex];
    const point = pointByKey.get(row.key);
    if (point) onRequestDelete(point);
    else setRows(previous => previous.filter((_, index) => index !== rowIndex));
  };

  const validateAndBuild = (): { changes: SaveChanges | null; errors: Set<string> } => {
    const errors = new Set<string>();
    const updates: SaveChanges["updates"] = [];
    const creates: DevicePointCreateRequest[] = [];

    rows.forEach((row, rowIndex) => {
      if (!isRowDirty(row)) return;
      const values = row.values;
      let rowHasError = false;
      const addError = (columnKey: ColumnKey) => { errors.add(cellKey(rowIndex, columnKey)); rowHasError = true; };

      if (values.name.trim() === "") addError("name");
      const size = Number(values.size);
      if (values.size.trim() === "" || !Number.isInteger(size) || size < 1) addError("size");
      if (!(DATA_TYPE as string[]).includes(values.data_type)) addError("data_type");
      if (values.address.trim() !== "") {
        const addressValue = Number(values.address);
        if (!Number.isInteger(addressValue) || addressValue < 0 || addressValue > 65535) addError("address");
      }
      if (values.scale_factor.trim() !== "" && Number.isNaN(Number(values.scale_factor))) addError("scale_factor");
      if (!CATEGORY.includes(values.category)) addError("category");
      if (values.poll_kind !== "" && !POLL_KIND.includes(values.poll_kind)) addError("poll_kind");
      if (!BYTE_ORDER.includes(values.byte_order)) addError("byte_order");
      if (!WORD_ORDER.includes(values.word_order)) addError("word_order");
      if (values.class !== "" && !(POINT_CLASS as string[]).includes(values.class)) addError("class");
      if (values.severity !== "" && !(SEVERITY as string[]).includes(values.severity)) addError("severity");
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

      const point = pointByKey.get(row.key);
      if (point) {
        updates.push({ id: point.id, payload });
      } else {
        creates.push({ ...payload, category: values.category as DevicePointCreateRequest["category"] } as DevicePointCreateRequest);
      }
    });

    if (errors.size > 0) return { changes: null, errors };
    return { changes: { updates, creates }, errors };
  };

  const handleSave = async () => {
    const { changes, errors } = validateAndBuild();
    setErrorCells(errors);
    if (!changes) return;
    if (changes.updates.length === 0 && changes.creates.length === 0) return;
    await onSave(changes);
  };

  return (
    <div className="space-y-3">
      <SpreadsheetGrid
        columns={COLUMNS}
        rows={rows}
        onRowsChange={setRows}
        newRowValues={EMPTY_VALUES}
        disabled={disabled}
        isCellEditable={isCellEditable}
        errorCells={errorCells}
        isRowDirty={isRowDirty}
        isRowNew={isRowNew}
        onDeleteRow={deleteRow}
        onDiscardAll={() => { if (dirtyCount > 0 && !isSaving) discard(); }}
        resetToken={resetToken}
        hint="Click a cell and type to edit. Drag to select, Ctrl+C / Ctrl+V to copy-paste, drag the corner handle to fill down. Use the filter row to narrow points."
        emptyMessage='No points yet. Click "Add Row" to create one.'
        noMatchMessage="No points match the filters."
        toolbar={(
          <>
            <Button type="button" variant="ghost" size="sm" className="gap-1" disabled={dirtyCount === 0 || isSaving} onClick={discard}>
              <Undo2 className="w-4 h-4" />Discard
            </Button>
            <Button type="button" size="sm" className="gap-1" disabled={disabled || dirtyCount === 0 || isSaving} onClick={handleSave}>
              <Save className="w-4 h-4" />{isSaving ? "Saving..." : `Save${dirtyCount ? ` (${dirtyCount})` : ""}`}
            </Button>
          </>
        )}
      />

      {errorCells.size > 0 && (
        <p className="text-xs text-destructive">
          {errorCells.size} invalid cell{errorCells.size > 1 ? "s" : ""} highlighted. Fix them before saving (Name &amp; Data Type required, Size ≥ 1, Address 0–65535).
        </p>
      )}
    </div>
  );
}
