import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Save, Share2 } from "lucide-react";
import { devicesApi } from "@/api";
import { cellKey, newRowKey, type GridColumn, type GridRow } from "@/shared/components/spreadsheet/grid";
import { SpreadsheetGrid } from "@/shared/components/spreadsheet/SpreadsheetGrid";
import type {
  ModbusByteOrder, ModbusLiveStreamRequest, ModbusRegisterConfig, ModbusWordOrder,
} from "@/shared/types/modbusLiveStream";

type RegisterDataType = ModbusRegisterConfig['data_type'];

// Every register data type the stream accepts (its contract enum). A Record, so a contract
// change fails the typecheck until this list matches.
const DATA_TYPE_SET: Record<RegisterDataType, true> = {
  int16: true, uint16: true, int32: true, uint32: true, float32: true, float64: true,
  int64: true, uint64: true, bool: true, raw: true,
};
const DATA_TYPES = Object.keys(DATA_TYPE_SET) as RegisterDataType[];
// backend-ot's default when a config omits data_type; sent explicitly (the contract requires it).
const DEFAULT_DATA_TYPE: RegisterDataType = 'int16';

const registerRowSchema = z.object({
  key: z.string(), // grid row identity; never sent
  address: z.string().min(1, 'Required'),
  label: z.string(),
  data_type: z.string(),
  byte_order: z.union([z.literal(''), z.literal('big'), z.literal('little')]),
  word_order: z.union([z.literal(''), z.literal('msw_first'), z.literal('lsw_first')]),
});

const formSchema = z.object({
  alias: z.string(),
  host: z.string().min(1, 'Host is required'),
  port: z.coerce.number().int().min(1).max(65535),
  server_address: z.coerce.number().int().min(0),
  kind: z.enum(['holding', 'input']),
  start_address: z.coerce.number().int().min(0),
  end_address: z.coerce.number().int().min(0),
  modbus_address_mode: z.enum(['zero_based', 'one_based']),
  interval: z.coerce.number().positive(),
  duration: z.coerce.number().int().positive(),
  byte_order: z.enum(['big', 'little']),
  word_order: z.enum(['msw_first', 'lsw_first']),
  registerConfigs: z.array(registerRowSchema),
}).refine(data => data.end_address >= data.start_address, {
  message: 'End address must be ≥ start address',
  path: ['end_address'],
}).refine(data => data.registerConfigs.every(row => {
  const addr = Number(row.address);
  return !Number.isNaN(addr) && addr >= data.start_address && addr <= data.end_address;
}), {
  message: 'Each register address must be within the start/end range',
  path: ['registerConfigs'],
});

type FormValues = z.infer<typeof formSchema>;
type RegisterRow = FormValues['registerConfigs'][number];
type RegisterColumnKey = 'address' | 'label' | 'data_type' | 'byte_order' | 'word_order';

// Empty enum cells mean "not set": int16 for data type, the session-wide order for byte/word order.
const REGISTER_COLUMNS: GridColumn<RegisterColumnKey>[] = [
  { key: 'address', label: 'Address', kind: 'number', minWidth: 'min-w-[90px]' },
  { key: 'label', label: 'Label', kind: 'text', minWidth: 'min-w-[160px]' },
  { key: 'data_type', label: 'Data Type', kind: 'enum', options: DATA_TYPES, optional: true, emptyLabel: `${DEFAULT_DATA_TYPE} (default)`, minWidth: 'min-w-[130px]' },
  { key: 'byte_order', label: 'Byte Order', kind: 'enum', options: ['big', 'little'], optional: true, emptyLabel: 'inherit', minWidth: 'min-w-[110px]' },
  { key: 'word_order', label: 'Word Order', kind: 'enum', options: ['msw_first', 'lsw_first'], optional: true, emptyLabel: 'inherit', minWidth: 'min-w-[110px]' },
];

const EMPTY_REGISTER_VALUES: Record<RegisterColumnKey, string> = {
  address: '', label: '', data_type: '', byte_order: '', word_order: '',
};

function emptyRow(address: string): RegisterRow {
  return { key: newRowKey(), address, label: '', data_type: '', byte_order: '', word_order: '' };
}

function toGridRow(row: RegisterRow): GridRow<RegisterColumnKey> {
  return {
    key: row.key,
    values: {
      address: row.address ?? '',
      label: row.label ?? '',
      data_type: row.data_type ?? '',
      byte_order: row.byte_order ?? '',
      word_order: row.word_order ?? '',
    },
  };
}

function fromGridRow(row: GridRow<RegisterColumnKey>): RegisterRow {
  return {
    key: row.key,
    ...row.values,
    byte_order: row.values.byte_order as RegisterRow['byte_order'],
    word_order: row.values.word_order as RegisterRow['word_order'],
  };
}

const defaultValues: FormValues = {
  alias: '',
  host: '',
  port: 502,
  server_address: 1,
  kind: 'holding',
  start_address: 0,
  end_address: 9,
  modbus_address_mode: 'zero_based',
  interval: 1,
  duration: 300,
  byte_order: 'big',
  word_order: 'msw_first',
  registerConfigs: [],
};

function toRequest(values: FormValues): ModbusLiveStreamRequest {
  const register_configs: ModbusLiveStreamRequest['register_configs'] = {};
  for (const row of values.registerConfigs) {
    // A row with nothing set is not sent; otherwise data_type is always included.
    if (!row.label && !row.data_type && !row.byte_order && !row.word_order) continue;
    register_configs[row.address] = {
      data_type: (row.data_type || DEFAULT_DATA_TYPE) as RegisterDataType,
      ...(row.label ? { label: row.label } : {}),
      ...(row.byte_order ? { byte_order: row.byte_order as ModbusByteOrder } : {}),
      ...(row.word_order ? { word_order: row.word_order as ModbusWordOrder } : {}),
    };
  }
  const { registerConfigs, alias, ...rest } = values;
  // formSchema requires every field; z.infer only marks them optional because tsconfig has
  // strictNullChecks off, so the cast restores what the schema already guarantees.
  return { ...(rest as Omit<ModbusLiveStreamRequest, 'register_configs'>), register_configs };
}

function fromRequest(request: ModbusLiveStreamRequest, alias: string): FormValues {
  const { register_configs, ...rest } = request;
  const registerConfigs: FormValues['registerConfigs'] = [];
  for (let addr = rest.start_address; addr <= rest.end_address; addr++) {
    const key = String(addr);
    const config = register_configs[key];
    registerConfigs.push({
      key: newRowKey(),
      address: key,
      label: config?.label ?? '',
      data_type: config?.data_type ?? '',
      byte_order: config?.byte_order ?? '',
      word_order: config?.word_order ?? '',
    });
  }
  return { ...rest, registerConfigs, alias };
}

const MAX_AUTO_ROWS = 500;

export function ModbusStreamForm({ siteId, initialValues, initialAlias, onSubmit }: {
  siteId: string | null;
  initialValues?: ModbusLiveStreamRequest;
  initialAlias?: string;
  onSubmit: (request: ModbusLiveStreamRequest, alias: string) => Promise<void>;
}) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { register, control, handleSubmit, setValue, getValues, watch, formState: { errors, isSubmitting, isSubmitted } } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: initialValues ? fromRequest(initialValues, initialAlias ?? '') : defaultValues,
  });

  const startAddress = Number(watch('start_address'));
  const endAddress = Number(watch('end_address'));
  const registerConfigs = watch('registerConfigs');

  const setRegisterRows = (rows: RegisterRow[]) =>
    setValue('registerConfigs', rows, { shouldDirty: true, shouldValidate: isSubmitted });

  // One row per address in start..end; rows already there (matched by address) keep their settings.
  useEffect(() => {
    if (!Number.isFinite(startAddress) || !Number.isFinite(endAddress) || endAddress < startAddress) return;
    if (endAddress - startAddress + 1 > MAX_AUTO_ROWS) return;
    const existingByAddress = new Map(getValues('registerConfigs').map(row => [row.address, row]));
    const next: RegisterRow[] = [];
    for (let addr = startAddress; addr <= endAddress; addr++) {
      const key = String(addr);
      next.push(existingByAddress.get(key) ?? emptyRow(key));
    }
    setValue('registerConfigs', next);
    // Intentionally re-runs only when the address range changes, not on every row edit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startAddress, endAddress]);

  const gridRows = useMemo(() => registerConfigs.map(toGridRow), [registerConfigs]);

  // Per-cell errors: a missing address from the schema, and (once submitted) any address outside start..end.
  const errorCells = useMemo(() => {
    const cells = new Set<string>();
    registerConfigs.forEach((row, index) => {
      if (errors.registerConfigs?.[index]?.address) cells.add(cellKey(index, 'address'));
      if (!isSubmitted) return;
      const address = Number(row.address);
      if (row.address === '' || Number.isNaN(address) || address < startAddress || address > endAddress) {
        cells.add(cellKey(index, 'address'));
      }
    });
    return cells;
  }, [registerConfigs, errors.registerConfigs, isSubmitted, startAddress, endAddress]);

  const { data: devices = [] } = useQuery({
    queryKey: ['site-devices', siteId],
    queryFn: () => devicesApi.getBySite(siteId!),
    enabled: !!siteId,
  });
  const modbusDevices = devices.filter(d => d.protocol?.toLowerCase() === 'modbus' && d.modbusConfig);

  const handleDeviceSelect = (deviceId: string) => {
    const device = modbusDevices.find(d => d.id === deviceId);
    if (!device?.modbusConfig) return;
    setValue('host', device.location);
    setValue('port', device.modbusConfig.port);
    setValue('server_address', device.modbusConfig.serverAddress);
    if (device.modbusConfig.addressMode === 'zero_based' || device.modbusConfig.addressMode === 'one_based') {
      setValue('modbus_address_mode', device.modbusConfig.addressMode);
    }
  };

  const onValid = async (values: FormValues) => {
    setSubmitError(null);
    try {
      await onSubmit(toRequest(values), values.alias.trim());
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to start session');
    }
  };

  return (
    <form onSubmit={handleSubmit(onValid)} className="space-y-4 border rounded-lg p-4 bg-card">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Connection Settings</h3>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" className="gap-1">
            <Share2 className="w-3 h-3" />Share Config
          </Button>
          <Button type="button" variant="outline" className="gap-1">
            <Save className="w-3 h-3" />Save Config
          </Button>
          <Button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Starting...' : 'Start Session'}</Button>
        </div>
      </div>
      {submitError && <p className="text-sm text-destructive">{submitError}</p>}

      <div className="space-y-1 max-w-sm">
        <Label htmlFor="alias">Alias (optional)</Label>
        <Input id="alias" placeholder="e.g. Plant A Boiler" {...register('alias')} />
      </div>

      {modbusDevices.length > 0 && (
        <div className="space-y-1">
          <Label>Prefill from device</Label>
          <Select onValueChange={handleDeviceSelect}>
            <SelectTrigger className="w-[280px]"><SelectValue placeholder="Select a Modbus device" /></SelectTrigger>
            <SelectContent>
              {modbusDevices.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1">
          <Label htmlFor="host">Host</Label>
          <Input id="host" {...register('host')} />
          {errors.host && <p className="text-xs text-destructive">{errors.host.message}</p>}
        </div>
        <div className="space-y-1">
          <Label htmlFor="port">Port</Label>
          <Input id="port" type="number" {...register('port')} />
          {errors.port && <p className="text-xs text-destructive">{errors.port.message}</p>}
        </div>
        <div className="space-y-1">
          <Label htmlFor="server_address">Server Address</Label>
          <Input id="server_address" type="number" {...register('server_address')} />
          {errors.server_address && <p className="text-xs text-destructive">{errors.server_address.message}</p>}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="space-y-1">
          <Label>Kind</Label>
          <Controller control={control} name="kind" render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="holding">Holding</SelectItem>
                <SelectItem value="input">Input</SelectItem>
              </SelectContent>
            </Select>
          )} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="start_address">Start Address</Label>
          <Input id="start_address" type="number" {...register('start_address')} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="end_address">End Address</Label>
          <Input id="end_address" type="number" {...register('end_address')} />
          {errors.end_address && <p className="text-xs text-destructive">{errors.end_address.message}</p>}
        </div>
        <div className="space-y-1">
          <Label>Address Mode</Label>
          <Controller control={control} name="modbus_address_mode" render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="zero_based">Zero-based</SelectItem>
                <SelectItem value="one_based">One-based</SelectItem>
              </SelectContent>
            </Select>
          )} />
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="space-y-1">
          <Label htmlFor="interval">Interval (s)</Label>
          <Input id="interval" type="number" step="0.1" {...register('interval')} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="duration">Duration (s)</Label>
          <Input id="duration" type="number" {...register('duration')} />
        </div>
        <div className="space-y-1">
          <Label>Byte Order</Label>
          <Controller control={control} name="byte_order" render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="big">Big</SelectItem>
                <SelectItem value="little">Little</SelectItem>
              </SelectContent>
            </Select>
          )} />
        </div>
        <div className="space-y-1">
          <Label>Word Order</Label>
          <Controller control={control} name="word_order" render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="msw_first">MSW first</SelectItem>
                <SelectItem value="lsw_first">LSW first</SelectItem>
              </SelectContent>
            </Select>
          )} />
        </div>
      </div>

      <div className="space-y-2">
        <div>
          <Label>Register Configs</Label>
          <p className="text-xs text-muted-foreground">Auto-filled from Start/End Address. Override label/type per register, or leave as default.</p>
        </div>
        {/* The range refine lands on the array itself (not .root: the rows aren't a useFieldArray). */}
        {(errors.registerConfigs?.root?.message ?? errors.registerConfigs?.message) && (
          <p className="text-xs text-destructive">{errors.registerConfigs?.root?.message ?? errors.registerConfigs?.message}</p>
        )}
        <SpreadsheetGrid
          columns={REGISTER_COLUMNS}
          rows={gridRows}
          onRowsChange={(rows) => setRegisterRows(rows.map(fromGridRow))}
          newRowValues={EMPTY_REGISTER_VALUES}
          errorCells={errorCells}
          emptyMessage='No registers. Set a Start/End Address or click "Add Row".'
          noMatchMessage="No registers match the filters."
        />
      </div>

    </form>
  );
}
