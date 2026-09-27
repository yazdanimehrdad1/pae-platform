import { useMemo } from "react";
import { getErrorMessage } from "@/api/client";
import type { GridColumn, GridRow } from "@/shared/components/spreadsheet/grid";
import { SpreadsheetGrid } from "@/shared/components/spreadsheet/SpreadsheetGrid";
import type { ModbusRegisterSnapshot } from "@/api/types/modbusStream";
import type { ModbusSessionState } from "../types";

// backend-ot keeps this many polls per session; the table always shows that many columns.
export const SNAPSHOT_SIZE = 10;
const EMPTY_VALUE = "None";
const MAX_ROWS_FROM_RANGE = 500;

const BASE_COLUMNS: GridColumn<string>[] = [
  { key: "address", label: "Address", kind: "number", minWidth: "min-w-[90px]" },
  { key: "label", label: "Label", kind: "text", minWidth: "min-w-[160px]" },
  { key: "data_type", label: "Data Type", kind: "text", minWidth: "min-w-[110px]" },
];

const pollKey = (index: number) => `poll_${index}`;

// backend-ot returns polls newest first; the table shows them oldest first, left to right, so
// column `index` holds poll `pollCount - 1 - index` of the response (none past pollCount).
const sourceIndex = (index: number, pollCount: number) => (index < pollCount ? pollCount - 1 - index : -1);

/**
 * A session's last polls, oldest to newest from the left, in exactly SNAPSHOT_SIZE columns: one
 * row per address of the session's range, "None" where no poll or value exists yet.
 */
export function RegisterSnapshotTable({ session, snapshot, error, takenAt }: {
  session: ModbusSessionState;
  snapshot: ModbusRegisterSnapshot | undefined;
  error: unknown;
  takenAt: number;
}) {
  const timestamps = snapshot?.timestamps;
  const columns = useMemo<GridColumn<string>[]>(() => [
    ...BASE_COLUMNS,
    ...Array.from({ length: SNAPSHOT_SIZE }, (_, index) => ({
      key: pollKey(index),
      label: timestamps?.[sourceIndex(index, timestamps.length)]
        ? new Date(timestamps[sourceIndex(index, timestamps.length)]).toLocaleTimeString()
        : "—",
      kind: "text" as const,
      align: "right" as const,
      minWidth: "min-w-[100px]",
    })),
  ], [timestamps]);

  const rows = useMemo<GridRow<string>[]>(() => {
    const pollCount = snapshot?.timestamps.length ?? 0;
    const entryByAddress = new Map((snapshot?.registers ?? []).map(entry => [String(entry.address), entry]));
    const addresses = new Set(entryByAddress.keys());
    if (session.end_address - session.start_address < MAX_ROWS_FROM_RANGE) {
      for (let address = session.start_address; address <= session.end_address; address++) addresses.add(String(address));
    }
    return [...addresses].sort((a, b) => Number(a) - Number(b)).map(address => {
      const entry = entryByAddress.get(address);
      const config = session.registerConfigs[address];
      const values: Record<string, string> = {
        address,
        label: config?.label ?? entry?.label ?? "",
        data_type: entry?.data_type ?? config?.data_type ?? "int16",
      };
      for (let index = 0; index < SNAPSHOT_SIZE; index++) {
        const value = entry?.values[sourceIndex(index, pollCount)];
        values[pollKey(index)] = value == null ? EMPTY_VALUE : String(value);
      }
      return { key: address, values };
    });
  }, [snapshot?.timestamps.length, snapshot?.registers, session.start_address, session.end_address, session.registerConfigs]);

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Last {SNAPSHOT_SIZE} polls, oldest to newest (left to right)
        {takenAt > 0 && <> · taken at {new Date(takenAt).toLocaleTimeString()}</>}
      </p>
      {error && <p className="text-sm text-destructive">{getErrorMessage(error, "Failed to take the snapshot")}</p>}
      <SpreadsheetGrid columns={columns} rows={rows} readOnly noMatchMessage="No registers match the filters." />
    </div>
  );
}
