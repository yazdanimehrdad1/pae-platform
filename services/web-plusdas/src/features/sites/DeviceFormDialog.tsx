import { Controller, useForm } from "react-hook-form";
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
import type { DeviceRecord, DeviceCreateRequest } from "@/shared/types/device";

const formSchema = z.object({
  name: z.string().min(1, "Required"),
  type: z.enum(["meter", "relay", "RTAC", "inverter", "BESS"]),
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
});

type FormValues = z.infer<typeof formSchema>;

const emptyValues: FormValues = {
  name: "",
  type: "meter",
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
};

function fromDevice(device: DeviceRecord): FormValues {
  return {
    name: device.name,
    type: device.type,
    protocol: device.protocol,
    vendor: device.vendor ?? "",
    model: device.model ?? "",
    host: device.host,
    port: device.port,
    timeout: device.timeout != null ? String(device.timeout) : "",
    server_address: device.server_address,
    description: device.description ?? "",
    poll_enabled: device.poll_enabled,
    read_from_aggregator: device.read_from_aggregator,
    modbus_address_mode: device.modbus_address_mode,
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

export function DeviceFormDialog({ open, onOpenChange, device, onSubmit }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  device?: DeviceRecord;
  onSubmit: (payload: DeviceCreateRequest) => Promise<void>;
}) {
  const { register, control, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    values: device ? fromDevice(device) : emptyValues,
  });

  const onValid = async (values: FormValues) => {
    try {
      await onSubmit(toRequest(values));
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
                    <SelectItem value="meter">Meter</SelectItem>
                    <SelectItem value="relay">Relay</SelectItem>
                    <SelectItem value="RTAC">RTAC</SelectItem>
                    <SelectItem value="inverter">Inverter</SelectItem>
                    <SelectItem value="BESS">BESS</SelectItem>
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

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving..." : "Save"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
