import { useMemo } from "react";
import type { GridColumn, GridRow } from "@/shared/components/spreadsheet/grid";
import { SpreadsheetGrid } from "@/shared/components/spreadsheet/SpreadsheetGrid";
import type { ModbusPolledRegister, ModbusRegisterConfig } from "@/shared/types/modbusLiveStream";

type ValueColumnKey = "address" | "label" | "data_type" | "value";

const COLUMNS: GridColumn<ValueColumnKey>[] = [
  { key: "address", label: "Address", kind: "number", minWidth: "min-w-[90px]" },
  { key: "label", label: "Label", kind: "text", minWidth: "min-w-[160px]" },
  { key: "data_type", label: "Data Type", kind: "text", minWidth: "min-w-[110px]" },
  { key: "value", label: "Value", kind: "text", align: "right", minWidth: "min-w-[120px]" },
];

/** Live values of a streaming session: read-only, but selectable, copyable and filterable. */
export function RegisterValuesTable({ registerConfigs, registers }: {
  registerConfigs: Record<string, ModbusRegisterConfig>;
  registers: Record<string, ModbusPolledRegister>;
}) {
  const rows = useMemo<GridRow<ValueColumnKey>[]>(() => {
    const addresses = Array.from(new Set([...Object.keys(registerConfigs), ...Object.keys(registers)]))
      .sort((a, b) => Number(a) - Number(b));
    return addresses.map(address => {
      const live = registers[address];
      const config = registerConfigs[address];
      return {
        key: address,
        values: {
          address,
          label: live?.label ?? config?.label ?? "",
          data_type: live?.data_type ?? config?.data_type ?? "",
          value: live ? String(live.value) : "",
        },
      };
    });
  }, [registerConfigs, registers]);

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No registers yet.</p>;
  }

  return (
    <SpreadsheetGrid
      columns={COLUMNS}
      rows={rows}
      readOnly
      noMatchMessage="No registers match the filters."
    />
  );
}
