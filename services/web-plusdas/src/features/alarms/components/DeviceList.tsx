import type { KeyboardEvent } from "react";
import { History } from "lucide-react";
import { cn } from "@/lib/utils";
import { SEVERITY } from "../lib/severity";
import type { Device, DeviceStatus } from "../types";
import { SeverityIndicator } from "./SeverityIndicator";

/**
 * Devices in the given (worst-first) order. Normal devices stay plain; those with events in the
 * last 6 h get a muted history mark.
 */
export function DeviceList({ devices: sorted, deviceStatus, devicesWithRecentEvents, selectedDeviceId, onSelect }: {
  devices: Device[];
  deviceStatus: Map<string, DeviceStatus>;
  devicesWithRecentEvents: Set<string>;
  selectedDeviceId: string | null;
  onSelect: (deviceId: string) => void;
}) {
  const onKeyDown = (event: KeyboardEvent<HTMLLIElement>, index: number) => {
    const next = event.key === "ArrowDown" ? index + 1 : event.key === "ArrowUp" ? index - 1 : null;
    if (next !== null && sorted[next]) {
      event.preventDefault();
      onSelect(sorted[next].id);
      (event.currentTarget.parentElement?.children[next] as HTMLElement | undefined)?.focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(sorted[index].id);
    }
  };

  return (
    <ul role="listbox" aria-label="Devices" className="divide-y divide-border rounded-md border border-border bg-card">
      {sorted.map((device, index) => {
        const status = deviceStatus.get(device.id) ?? "normal";
        const selected = device.id === selectedDeviceId;
        return (
          <li
            key={device.id}
            role="option"
            aria-selected={selected}
            tabIndex={selected || (!selectedDeviceId && index === 0) ? 0 : -1}
            onClick={() => onSelect(device.id)}
            onKeyDown={event => onKeyDown(event, index)}
            className={cn(
              "flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
              selected ? "bg-muted" : "hover:bg-muted/50",
            )}
          >
            <span className={cn("truncate", status !== "normal" && ["font-semibold", SEVERITY[status].textClass])}>{device.name}</span>
            {status !== "normal" ? (
              <SeverityIndicator severity={status} showLabel={false} />
            ) : devicesWithRecentEvents.has(device.id) ? (
              <span className="text-muted-foreground" title="Had events in the last 6 h">
                <History aria-hidden className="h-3.5 w-3.5" />
                <span className="sr-only">Had events in the last 6 h</span>
              </span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
