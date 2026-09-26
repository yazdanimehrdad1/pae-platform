// Types and helpers shared by SpreadsheetGrid and its users (kept out of the component file
// so React fast refresh works).

export type GridColumnKind = "text" | "number" | "enum";

export interface GridColumn<K extends string> {
  key: K;
  label: string;
  kind: GridColumnKind;
  /** Allowed values of an enum column. */
  options?: readonly string[];
  /** An enum cell may be left empty. */
  optional?: boolean;
  /** Shown for an empty optional cell (default "—"). */
  emptyLabel?: string;
  /** `step` of a number cell's input (default "1"). */
  step?: string;
  align?: "left" | "right";
  minWidth: string;
}

export interface GridRow<K extends string> {
  /** Stable React key; also how the parent tells rows apart. */
  key: string;
  values: Record<K, string>;
}

let nextNewRowNumber = 1;
/** A key for a row that doesn't exist anywhere else yet. */
export function newRowKey(): string {
  return `new-${nextNewRowNumber++}`;
}

/** Number cells accept only numeric (or empty) text; enum cells only their options (any casing). */
export function normalizeForColumn<K extends string>(column: GridColumn<K>, rawValue: string): string | null {
  const value = rawValue.trim();
  if (column.kind === "number") return value === "" || !Number.isNaN(Number(value)) ? value : null;
  if (column.kind === "enum") {
    if (value === "") return column.optional ? "" : null;
    const match = (column.options ?? []).find(option => option.toLowerCase() === value.toLowerCase());
    return match ?? null;
  }
  return rawValue;
}

/** Key of a cell in `errorCells`. */
export function cellKey(rowIndex: number, columnKey: string): string {
  return `${rowIndex}:${columnKey}`;
}
