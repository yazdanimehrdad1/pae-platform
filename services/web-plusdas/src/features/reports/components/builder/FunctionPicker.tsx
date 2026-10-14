import type { ReportSiteFunction } from "@/api/types/reports";
import type { DevicePointsEntry } from "@/api/types/devices";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/** The devices a device function applies to (every device when it names no types). */
function devicesFor(siteFunction: ReportSiteFunction, devices: DevicePointsEntry[]): DevicePointsEntry[] {
  if (siteFunction.kind !== "device") return [];
  const types: string[] = siteFunction.device_types ?? [];
  return types.length === 0 ? devices : devices.filter(device => types.includes(device.deviceType));
}

/** A site function (and, for a device function, the device it runs on). */
export function FunctionPicker({ functions, devices, name, deviceId, onChange, ariaLabel }: {
  functions: ReportSiteFunction[];
  devices: DevicePointsEntry[];
  name: string;
  deviceId: number | null | undefined;
  onChange: (name: string, deviceId: number | null) => void;
  ariaLabel: string;
}) {
  const chosen = functions.find(candidate => candidate.name === name);
  const usableDevices = chosen ? devicesFor(chosen, devices) : [];
  const pickFunction = (picked: string) => {
    const next = functions.find(candidate => candidate.name === picked);
    onChange(picked, next?.kind === "device" ? (devicesFor(next, devices)[0]?.deviceId ?? null) : null);
  };

  if (functions.length === 0) {
    return <p className="text-sm text-muted-foreground">This site's profile offers no site functions.</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      <Select value={name || undefined} onValueChange={pickFunction}>
        <SelectTrigger aria-label={ariaLabel} className="w-64"><SelectValue placeholder="Choose a function" /></SelectTrigger>
        <SelectContent>
          {functions.map(candidate => <SelectItem key={candidate.name} value={candidate.name}>{candidate.summary || candidate.name}</SelectItem>)}
        </SelectContent>
      </Select>
      {chosen?.kind === "device" && (
        <Select value={deviceId ? String(deviceId) : undefined} onValueChange={value => onChange(name, Number(value))}>
          <SelectTrigger aria-label={`${ariaLabel} device`} className="w-48"><SelectValue placeholder="Choose a device" /></SelectTrigger>
          <SelectContent>
            {usableDevices.map(device => <SelectItem key={device.deviceId} value={String(device.deviceId)}>{device.deviceName}</SelectItem>)}
          </SelectContent>
        </Select>
      )}
    </div>
  );
}
