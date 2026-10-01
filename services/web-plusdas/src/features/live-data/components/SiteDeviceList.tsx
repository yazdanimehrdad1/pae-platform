import type { KeyboardEvent } from "react";
import type { DevicePointsEntry } from "@/api/types/devices";
import { cn } from "@/lib/utils";

/** The site's devices, one selectable at a time (click, Enter/Space, or arrow keys). */
export function SiteDeviceList({ devices, selectedDeviceId, onSelect }: {
  devices: DevicePointsEntry[];
  selectedDeviceId: number | null;
  onSelect: (deviceId: number) => void;
}) {
  const onKeyDown = (event: KeyboardEvent<HTMLLIElement>, index: number) => {
    const next = event.key === "ArrowDown" ? index + 1 : event.key === "ArrowUp" ? index - 1 : null;
    if (next !== null && devices[next]) {
      event.preventDefault();
      onSelect(devices[next].deviceId);
      (event.currentTarget.parentElement?.children[next] as HTMLElement | undefined)?.focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(devices[index].deviceId);
    }
  };

  return (
    <ul role="listbox" aria-label="Devices" className="divide-y divide-border rounded-md border border-border">
      {devices.map((device, index) => {
        const selected = device.deviceId === selectedDeviceId;
        return (
          <li
            key={device.deviceId}
            role="option"
            aria-selected={selected}
            tabIndex={selected || (selectedDeviceId === null && index === 0) ? 0 : -1}
            onClick={() => onSelect(device.deviceId)}
            onKeyDown={event => onKeyDown(event, index)}
            className={cn(
              "flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
              selected ? "bg-muted font-medium" : "hover:bg-muted/50",
            )}
          >
            <span className="truncate">{device.deviceName}</span>
            <span className="text-xs tabular-nums text-muted-foreground">{device.points.length} points</span>
          </li>
        );
      })}
    </ul>
  );
}
