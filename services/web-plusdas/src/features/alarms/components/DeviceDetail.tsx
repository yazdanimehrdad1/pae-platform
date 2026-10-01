import { useMemo } from "react";
import { watchedPointId, type AlarmModel } from "../lib/alarmModel";
import type { AlarmLogEntry, Device, DeviceStatus, Rule } from "../types";
import { EventLog } from "./EventLog";
import { SeverityIndicator } from "./SeverityIndicator";
import type { TrendRange } from "../lib/trendRange";
import { TrendChart } from "./TrendChart";

const DEFAULT_STALE_AFTER_SEC = 60;

/** The selected device: identity and poll health, trend of one point, its events of the last 6 h. */
export function DeviceDetail({ siteId, device, status, model, rules, log, now, timeZone, selectedPointId, trendRange, onTrendRangeChange }: {
  siteId: string;
  device: Device;
  status: DeviceStatus;
  model: AlarmModel;
  rules: Rule[];
  log: AlarmLogEntry[];
  now: number;
  timeZone: string;
  selectedPointId: string | null;
  trendRange: TrendRange;
  onTrendRangeChange: (range: TrendRange) => void;
}) {
  const points = useMemo(() => [...model.pointsById.values()].filter(point => point.deviceId === device.id), [model, device.id]);
  const limitsByPoint = useMemo(() => {
    const limits = new Map<string, Rule[]>();
    for (const rule of rules) {
      const pointId = watchedPointId(rule);
      if (pointId && rule.enabled) limits.set(pointId, [...(limits.get(pointId) ?? []), rule]);
    }
    return limits;
  }, [rules]);

  const staleRule = rules.find(rule => rule.enabled && rule.rule?.kind === "comms_stale" && String(rule.rule.device_id) === device.id);
  const staleAfterSec = staleRule?.rule?.kind === "comms_stale" ? staleRule.rule.stale_after_sec : DEFAULT_STALE_AFTER_SEC;
  const polledSecondsAgo = device.lastPollAt ? Math.max(0, Math.round((now - Date.parse(device.lastPollAt)) / 1000)) : null;
  const isPollStale = polledSecondsAgo === null || polledSecondsAgo > staleAfterSec;
  const trendPoint = points.find(point => point.id === selectedPointId && point.kind === "numeric") ?? null;
  const deviceLog = log.filter(entry => entry.deviceId === device.id);

  return (
    <section aria-labelledby="device-detail-heading" className="space-y-5 rounded-md border border-border bg-card p-4">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 id="device-detail-heading" className="text-base font-semibold">{device.name}</h2>
          {status === "normal"
            ? <span className="text-sm text-muted-foreground">Normal</span>
            : <SeverityIndicator severity={status} className="text-sm" />}
          <span className="text-sm text-muted-foreground">
            {device.protocol} · {device.host}:{device.port} · unit {device.unitId}
          </span>
        </div>
        {isPollStale ? (
          <span className="inline-flex items-center gap-1.5 text-sm">
            <SeverityIndicator severity="warning" showLabel={false} />
            <span className="text-alarm-warning">
              {polledSecondsAgo === null ? "No successful poll stored" : `Poll stale: last ${polledSecondsAgo} s ago`}
            </span>
          </span>
        ) : (
          <span className="text-sm tabular-nums text-muted-foreground">Polled {polledSecondsAgo} s ago</span>
        )}
      </header>

      {trendPoint ? (
        <TrendChart siteId={siteId} point={trendPoint} limits={limitsByPoint.get(trendPoint.id) ?? []} now={now} timeZone={timeZone}
          range={trendRange} onRangeChange={onTrendRangeChange} />
      ) : (
        <p className="text-sm text-muted-foreground">This device has no numeric point to trend.</p>
      )}

      <div>
        <h3 className="mb-1 text-sm font-medium">Events, last 6 h</h3>
        <EventLog entries={deviceLog} timeZone={timeZone} />
      </div>
    </section>
  );
}
