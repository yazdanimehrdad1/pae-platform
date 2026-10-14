import { getErrorMessage } from "@/api/client";
import type { ActivePointAlarm, DeviceAlarmStatus } from "@/api/types/sites";
import { Badge } from "@/components/ui/badge";
import { pointSeverityStyle } from "../lib/pointSeverity";
import { useSiteHealth } from "../hooks/useSiteHealth";

function neverReportedNote(count: number | undefined): string | null {
  if (!count) return null;
  return `${count} ${count === 1 ? "point" : "points"} never reported`;
}

function AlarmRow({ alarm }: { alarm: ActivePointAlarm }) {
  const { label, Icon, textClass } = pointSeverityStyle(alarm.severity);
  return (
    <li className="flex flex-wrap items-center gap-2 text-sm">
      <span className={`inline-flex items-center gap-1 font-medium min-w-[84px] ${textClass}`}>
        <Icon className="w-4 h-4" aria-hidden />
        {label}
      </span>
      <span className="font-medium">{alarm.device_point_name}</span>
      {alarm.enum_label && <span className="text-muted-foreground">{alarm.enum_label}</span>}
      {(alarm.active_bits ?? []).map((bit) => (
        <Badge key={bit} variant="outline" className="font-mono text-[11px]">
          {bit}
        </Badge>
      ))}
    </li>
  );
}

function DeviceSection({ device }: { device: DeviceAlarmStatus }) {
  const alarms = device.active_alarms ?? [];
  const note = neverReportedNote(device.unknown_count);
  return (
    <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-2 py-2">
      <div className="text-sm font-semibold truncate">{device.device_name}</div>
      <div className="space-y-1">
        {alarms.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active alarms</p>
        ) : (
          <ul className="space-y-1">
            {alarms.map((alarm) => (
              <AlarmRow key={alarm.device_point_id} alarm={alarm} />
            ))}
          </ul>
        )}
        {note && <p className="text-xs text-muted-foreground">{note}</p>}
      </div>
    </div>
  );
}

// A site's set ALARM-class points, per device, shown while the site bar is open. The per-severity
// counts are on the bar itself (SiteHealthCounts).
export function SiteHealthPanel({ siteId }: { siteId: string }) {
  const { data: health, isLoading, error } = useSiteHealth(siteId);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        Loading site health…
      </div>
    );
  }
  if (error || !health) {
    return <p className="text-sm text-destructive">{getErrorMessage(error, "Failed to load site health")}</p>;
  }

  const devices = health.devices ?? [];
  const note = neverReportedNote(health.unknown_count);
  return (
    <div className="space-y-2">
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
      {devices.length === 0 ? (
        <p className="text-sm text-muted-foreground">This site has no devices</p>
      ) : (
        <div className="divide-y divide-border">
          {devices.map((device) => (
            <DeviceSection key={device.device_id} device={device} />
          ))}
        </div>
      )}
    </div>
  );
}
