import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ModbusPolledRegister, ModbusRegisterConfig } from "@/shared/types/modbusLiveStream";

export function RegisterValuesTable({ registerConfigs, registers }: {
  registerConfigs: Record<string, ModbusRegisterConfig>;
  registers: Record<string, ModbusPolledRegister>;
}) {
  const addresses = Array.from(new Set([...Object.keys(registerConfigs), ...Object.keys(registers)]))
    .sort((a, b) => Number(a) - Number(b));

  if (addresses.length === 0) {
    return <p className="text-sm text-muted-foreground">No registers yet.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Address</TableHead>
          <TableHead>Label</TableHead>
          <TableHead>Data Type</TableHead>
          <TableHead className="text-right">Value</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {addresses.map(address => {
          const live = registers[address];
          const config = registerConfigs[address];
          return (
            <TableRow key={address}>
              <TableCell className="tabular-nums">{address}</TableCell>
              <TableCell>{live?.label ?? config?.label ?? '—'}</TableCell>
              <TableCell>{live?.data_type ?? config?.data_type ?? '—'}</TableCell>
              <TableCell className="text-right tabular-nums">{live ? live.value : '—'}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
