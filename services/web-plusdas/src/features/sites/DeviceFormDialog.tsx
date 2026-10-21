import { Controller, useForm, type UseFormRegister } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import type {
  DeviceRecord, DeviceCreateRequest, DeviceType, PvArrayConfig, PvArrayConfigRequest,
} from "@/api/types/devices";
import { supportsPvArray } from "./hooks/useDevicePvArray";

// Every device type backend-ot accepts (its contract enum). A Record, so adding or removing
// a type in the contract fails the typecheck until this list matches.
const DEVICE_TYPE_LABELS: Record<DeviceType, string> = {
  METER: "Meter",
  RELAY: "Relay",
  RTAC: "RTAC",
  IED: "IED",
  INVERTER: "Inverter",
  PV: "PV",
  BESS: "BESS",
  ES: "Energy storage",
  GENERATOR: "Generator",
  LOADBANK: "Load bank",
};
const DEVICE_TYPES = Object.keys(DEVICE_TYPE_LABELS) as [DeviceType, ...DeviceType[]];

// Responses carry type/protocol/address mode as plain strings (backend-ot returns them in
// canonical form); narrow them to the request enums for the form.
function toDeviceType(value: string): DeviceType {
  const upper = value.toUpperCase();
  return (DEVICE_TYPES as string[]).includes(upper) ? (upper as DeviceType) : "METER";
}

const formSchema = z.object({
  name: z.string().min(1, "Required"),
  type: z.enum(DEVICE_TYPES),
  protocol: z.enum(["Modbus", "DNP"]),
  vendor: z.string(),
  model: z.string(),
  host: z.string().min(1, "Required"),
  port: z.coerce.number().int().min(1).max(65535),
  timeout: z.string(),
  server_address: z.coerce.number().int().min(1),
  description: z.string(),
  poll_enabled: z.boolean(),
  read_from_aggregator: z.boolean(),
  modbus_address_mode: z.enum(["zero_based", "one_based"]),
  // PV array (PV and INVERTER devices only), for the PV forecast. All blank means none.
  pv_tilt_deg: z.string(),
  pv_azimuth_deg: z.string(),
  pv_dc_capacity_kw: z.string(),
  pv_ac_capacity_kw: z.string(),
  pv_system_loss_pct: z.string(),
  pv_temp_coefficient_pct_per_c: z.string(),
}).superRefine((values, ctx) => {
  if (!supportsPvArray(values.type) || !hasPvArray(values)) return;
  for (const field of PV_FIELDS) {
    const { min, max, required } = PV_FIELD_RULES[field];
    const raw = (values[field] ?? "").trim();
    if (raw === "" && !required) continue;
    const value = Number(raw);
    if (raw === "" || Number.isNaN(value) || value < min || value > max) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: [field], message: `Enter ${min} to ${max}` });
    }
  }
});

type PvField =
  | "pv_tilt_deg" | "pv_azimuth_deg" | "pv_dc_capacity_kw" | "pv_ac_capacity_kw"
  | "pv_system_loss_pct" | "pv_temp_coefficient_pct_per_c";

// The limits backend-ot enforces (PvArrayConfigUpsertRequest). Azimuth: clockwise from north,
// 180 = south; backend-ot excludes 360 itself.
const PV_FIELD_RULES: Record<PvField, { min: number; max: number; required: boolean }> = {
  pv_tilt_deg: { min: 0, max: 90, required: true },
  pv_azimuth_deg: { min: 0, max: 359.99, required: true },
  pv_dc_capacity_kw: { min: 0.001, max: 1_000_000, required: true },
  pv_ac_capacity_kw: { min: 0.001, max: 1_000_000, required: true },
  pv_system_loss_pct: { min: 0, max: 99.99, required: false },
  pv_temp_coefficient_pct_per_c: { min: -2, max: 0, required: false },
};
const PV_FIELDS = Object.keys(PV_FIELD_RULES) as PvField[];

// Partial: z.infer marks every field optional under this tsconfig (see CLAUDE.md).
function hasPvArray(values: Partial<Record<PvField, string>>): boolean {
  return PV_FIELDS.some((field) => (values[field] ?? "").trim() !== "");
}

// backend-ot's defaults (PvArrayConfigUpsertRequest), sent when the field is left blank.
const DEFAULT_SYSTEM_LOSS_PCT = 14;
const DEFAULT_TEMP_COEFFICIENT_PCT_PER_C = -0.35;

function numberOr(raw: string, fallback: number): number {
  return raw.trim() === "" ? fallback : Number(raw);
}

type FormValues = z.infer<typeof formSchema>;

const emptyValues: FormValues = {
  name: "",
  type: "METER",
  protocol: "Modbus",
  vendor: "",
  model: "",
  host: "",
  port: 502,
  timeout: "",
  server_address: 1,
  description: "",
  poll_enabled: true,
  read_from_aggregator: true,
  modbus_address_mode: "zero_based",
  pv_tilt_deg: "",
  pv_azimuth_deg: "",
  pv_dc_capacity_kw: "",
  pv_ac_capacity_kw: "",
  pv_system_loss_pct: "",
  pv_temp_coefficient_pct_per_c: "",
};

function fromDevice(device: DeviceRecord, pvArray: PvArrayConfig | null | undefined): FormValues {
  return {
    name: device.name,
    type: toDeviceType(device.type),
    protocol: device.protocol as DeviceCreateRequest["protocol"],
    vendor: device.vendor ?? "",
    model: device.model ?? "",
    host: device.host,
    port: device.port,
    timeout: device.timeout != null ? String(device.timeout) : "",
    server_address: device.server_address,
    description: device.description ?? "",
    poll_enabled: device.poll_enabled,
    read_from_aggregator: device.read_from_aggregator,
    modbus_address_mode: device.modbus_address_mode as DeviceCreateRequest["modbus_address_mode"],
    pv_tilt_deg: pvArray ? String(pvArray.tilt_deg) : "",
    pv_azimuth_deg: pvArray ? String(pvArray.azimuth_deg) : "",
    pv_dc_capacity_kw: pvArray ? String(pvArray.dc_capacity_kw) : "",
    pv_ac_capacity_kw: pvArray ? String(pvArray.ac_capacity_kw) : "",
    pv_system_loss_pct: pvArray ? String(pvArray.system_loss_pct) : "",
    pv_temp_coefficient_pct_per_c: pvArray ? String(pvArray.temp_coefficient_pct_per_c) : "",
  };
}

/** The PV array to save, or null for none (blank fields, or not a PV/INVERTER device). */
function toPvArray(values: FormValues): PvArrayConfigRequest | null {
  if (!supportsPvArray(values.type) || !hasPvArray(values)) return null;
  return {
    tilt_deg: Number(values.pv_tilt_deg),
    azimuth_deg: Number(values.pv_azimuth_deg),
    dc_capacity_kw: Number(values.pv_dc_capacity_kw),
    ac_capacity_kw: Number(values.pv_ac_capacity_kw),
    system_loss_pct: numberOr(values.pv_system_loss_pct, DEFAULT_SYSTEM_LOSS_PCT),
    temp_coefficient_pct_per_c: numberOr(
      values.pv_temp_coefficient_pct_per_c, DEFAULT_TEMP_COEFFICIENT_PCT_PER_C,
    ),
  };
}

function toRequest(values: FormValues): DeviceCreateRequest {
  const payload: DeviceCreateRequest = {
    name: values.name,
    type: values.type,
    protocol: values.protocol,
    host: values.host,
    port: values.port,
    server_address: values.server_address,
    poll_enabled: values.poll_enabled,
    read_from_aggregator: values.read_from_aggregator,
    modbus_address_mode: values.modbus_address_mode,
  };
  if (values.vendor.trim()) payload.vendor = values.vendor.trim();
  if (values.model.trim()) payload.model = values.model.trim();
  if (values.description.trim()) payload.description = values.description.trim();
  if (values.timeout.trim() !== "") payload.timeout = Number(values.timeout);
  return payload;
}

export function DeviceFormDialog({ open, onOpenChange, device, pvArray, onSubmit }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  device?: DeviceRecord;
  // The device's current PV array (PV/INVERTER devices); null or omitted = none.
  pvArray?: PvArrayConfig | null;
  // pvArray: the PV array to save, or null for none (the caller deletes an existing one).
  onSubmit: (payload: DeviceCreateRequest, pvArray: PvArrayConfigRequest | null) => Promise<void>;
}) {
  const { register, control, handleSubmit, reset, watch, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    values: device ? fromDevice(device, pvArray) : emptyValues,
  });
  const showPvArray = supportsPvArray(watch("type"));

  const onValid = async (values: FormValues) => {
    try {
      await onSubmit(toRequest(values), toPvArray(values));
      reset();
      onOpenChange(false);
    } catch {
      // error is reported to the user by the caller's mutation
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{device ? "Edit Device" : "Add Device"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onValid)} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Controller control={control} name="type" render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {DEVICE_TYPES.map((deviceType) => (
                      <SelectItem key={deviceType} value={deviceType}>{DEVICE_TYPE_LABELS[deviceType]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="vendor">Vendor</Label>
              <Input id="vendor" {...register("vendor")} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="model">Model</Label>
              <Input id="model" {...register("model")} />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" {...register("description")} />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label htmlFor="host">Host</Label>
              <Input id="host" {...register("host")} />
              {errors.host && <p className="text-xs text-destructive">{errors.host.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="port">Port</Label>
              <Input id="port" type="number" {...register("port")} />
              {errors.port && <p className="text-xs text-destructive">{errors.port.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="server_address">Server Address</Label>
              <Input id="server_address" type="number" {...register("server_address")} />
              {errors.server_address && <p className="text-xs text-destructive">{errors.server_address.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label>Protocol</Label>
              <Controller control={control} name="protocol" render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Modbus">Modbus</SelectItem>
                    <SelectItem value="DNP">DNP</SelectItem>
                  </SelectContent>
                </Select>
              )} />
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
            <div className="space-y-1">
              <Label htmlFor="timeout">Timeout (s, optional)</Label>
              <Input id="timeout" type="number" step="any" {...register("timeout")} />
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Controller control={control} name="poll_enabled" render={({ field }) => (
                <Checkbox id="poll_enabled" checked={field.value} onCheckedChange={(c) => field.onChange(c === true)} />
              )} />
              <Label htmlFor="poll_enabled">Poll Enabled</Label>
            </div>
            <div className="flex items-center gap-2">
              <Controller control={control} name="read_from_aggregator" render={({ field }) => (
                <Checkbox id="read_from_aggregator" checked={field.value} onCheckedChange={(c) => field.onChange(c === true)} />
              )} />
              <Label htmlFor="read_from_aggregator">Read From Aggregator</Label>
            </div>
          </div>

          {showPvArray && (
            <fieldset className="space-y-3 rounded-md border p-3">
              <legend className="px-1 text-sm font-medium">PV array (for the PV forecast)</legend>
              <p className="text-xs text-muted-foreground">
                Leave blank if this device has no PV array. Azimuth is clockwise from north (180 = south).
              </p>
              <div className="grid grid-cols-2 gap-3">
                <PvInput id="pv_tilt_deg" label="Tilt (deg)" register={register} error={errors.pv_tilt_deg?.message} />
                <PvInput id="pv_azimuth_deg" label="Azimuth (deg)" register={register} error={errors.pv_azimuth_deg?.message} />
                <PvInput id="pv_dc_capacity_kw" label="DC capacity (kWp)" register={register} error={errors.pv_dc_capacity_kw?.message} />
                <PvInput id="pv_ac_capacity_kw" label="AC capacity (kW)" register={register} error={errors.pv_ac_capacity_kw?.message} />
                <PvInput id="pv_system_loss_pct" label="System losses (%, default 14)" register={register} error={errors.pv_system_loss_pct?.message} />
                <PvInput id="pv_temp_coefficient_pct_per_c" label="Temp. coefficient (%/°C, default -0.35)" register={register} error={errors.pv_temp_coefficient_pct_per_c?.message} />
              </div>
            </fieldset>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving..." : "Save"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PvInput({ id, label, register, error }: {
  id: PvField;
  label: string;
  register: UseFormRegister<FormValues>;
  error?: string;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" step="any" {...register(id)} />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
