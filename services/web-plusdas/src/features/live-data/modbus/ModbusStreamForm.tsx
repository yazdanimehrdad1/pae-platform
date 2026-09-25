import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Save, Share2, Trash2 } from "lucide-react";
import { devicesApi } from "@/api";
import type { ModbusByteOrder, ModbusLiveStreamRequest, ModbusWordOrder } from "@/shared/types/modbusLiveStream";

const DATA_TYPES = ['int16', 'uint16', 'int32', 'uint32', 'float32', 'float64', 'int64', 'uint64'];
const DEFAULT_DATA_TYPE = 'int16';
const NONE_VALUE = '__none__';

const registerRowSchema = z.object({
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
  kind: z.enum(['holding', 'input', 'coils']),
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
    const config = {
      ...(row.label ? { label: row.label } : {}),
      ...(row.data_type ? { data_type: row.data_type } : {}),
      ...(row.byte_order ? { byte_order: row.byte_order as ModbusByteOrder } : {}),
      ...(row.word_order ? { word_order: row.word_order as ModbusWordOrder } : {}),
    };
    if (Object.keys(config).length > 0) register_configs[row.address] = config;
  }
  const { registerConfigs, alias, ...rest } = values;
  return { ...rest, register_configs };
}

function fromRequest(request: ModbusLiveStreamRequest, alias: string): FormValues {
  const { register_configs, ...rest } = request;
  const registerConfigs: FormValues['registerConfigs'] = [];
  for (let addr = rest.start_address; addr <= rest.end_address; addr++) {
    const key = String(addr);
    const config = register_configs[key];
    registerConfigs.push({
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
  onSubmit: (request: ModbusLiveStreamRequest, alias: string) => Promise<string>;
}) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { register, control, handleSubmit, setValue, watch, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: initialValues ? fromRequest(initialValues, initialAlias ?? '') : defaultValues,
  });
  const { fields, append, remove, replace } = useFieldArray({ control, name: 'registerConfigs' });

  const startAddress = Number(watch('start_address'));
  const endAddress = Number(watch('end_address'));

  useEffect(() => {
    if (!Number.isFinite(startAddress) || !Number.isFinite(endAddress) || endAddress < startAddress) return;
    if (endAddress - startAddress + 1 > MAX_AUTO_ROWS) return;
    const existingByAddress = new Map(fields.map(row => [row.address, row]));
    const next = [];
    for (let addr = startAddress; addr <= endAddress; addr++) {
      const key = String(addr);
      const existingRow = existingByAddress.get(key);
      next.push(existingRow
        ? { address: existingRow.address, label: existingRow.label, data_type: existingRow.data_type, byte_order: existingRow.byte_order, word_order: existingRow.word_order }
        : { address: key, label: '', data_type: '', byte_order: '' as const, word_order: '' as const });
    }
    replace(next);
    // Intentionally re-runs only when the address range changes, not when `fields`/`replace` identity changes (replace() itself updates `fields`).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startAddress, endAddress]);

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
                <SelectItem value="coils">Coils</SelectItem>
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
        <div className="flex items-center justify-between">
          <div>
            <Label>Register Configs</Label>
            <p className="text-xs text-muted-foreground">Auto-filled from Start/End Address. Override label/type per register, or leave as default.</p>
          </div>
          <Button type="button" variant="outline" size="sm" className="gap-1"
            onClick={() => append({ address: '', label: '', data_type: '', byte_order: '', word_order: '' })}>
            <Plus className="w-3 h-3" />Add Row
          </Button>
        </div>
        {errors.registerConfigs?.root && <p className="text-xs text-destructive">{errors.registerConfigs.root.message}</p>}
        {fields.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Address</TableHead>
                <TableHead>Label (optional)</TableHead>
                <TableHead>Data Type</TableHead>
                <TableHead>Byte Order</TableHead>
                <TableHead>Word Order</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {fields.map((field, index) => (
                <TableRow key={field.id}>
                  <TableCell><Input className="h-8 w-20" {...register(`registerConfigs.${index}.address`)} /></TableCell>
                  <TableCell><Input className="h-8 w-32" placeholder="(optional)" {...register(`registerConfigs.${index}.label`)} /></TableCell>
                  <TableCell>
                    <Controller control={control} name={`registerConfigs.${index}.data_type`} render={({ field: f }) => (
                      <Select value={f.value || NONE_VALUE} onValueChange={(v) => f.onChange(v === NONE_VALUE ? '' : v)}>
                        <SelectTrigger className="h-8 w-28"><SelectValue placeholder={DEFAULT_DATA_TYPE} /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value={NONE_VALUE}>{DEFAULT_DATA_TYPE}</SelectItem>
                          {DATA_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    )} />
                  </TableCell>
                  <TableCell>
                    <Controller control={control} name={`registerConfigs.${index}.byte_order`} render={({ field: f }) => (
                      <Select value={f.value || NONE_VALUE} onValueChange={(v) => f.onChange(v === NONE_VALUE ? '' : v)}>
                        <SelectTrigger className="h-8 w-24"><SelectValue placeholder="inherit" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value={NONE_VALUE}>inherit</SelectItem>
                          <SelectItem value="big">big</SelectItem>
                          <SelectItem value="little">little</SelectItem>
                        </SelectContent>
                      </Select>
                    )} />
                  </TableCell>
                  <TableCell>
                    <Controller control={control} name={`registerConfigs.${index}.word_order`} render={({ field: f }) => (
                      <Select value={f.value || NONE_VALUE} onValueChange={(v) => f.onChange(v === NONE_VALUE ? '' : v)}>
                        <SelectTrigger className="h-8 w-28"><SelectValue placeholder="inherit" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value={NONE_VALUE}>inherit</SelectItem>
                          <SelectItem value="msw_first">msw_first</SelectItem>
                          <SelectItem value="lsw_first">lsw_first</SelectItem>
                        </SelectContent>
                      </Select>
                    )} />
                  </TableCell>
                  <TableCell>
                    <Button type="button" variant="ghost" size="icon" className="h-8 w-8" onClick={() => remove(index)}>
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

    </form>
  );
}
