import { useMemo } from "react";
import type { AlarmModel } from "../lib/alarmModel";
import type { AlarmLogEntry, Device, DeviceStatus, Rule, Severity, ThresholdRule } from "../types";
import { EventLog } from "./EventLog";
import { PointsTable } from "./PointsTable";
import { SeverityIndicator } from "./SeverityIndicator";
import type { TrendRange } from "../lib/trendRange";
import { TrendChart } from "./TrendChart";

const PROTOCOL_LABEL: Record<Device["protocol"], string> = { modbus_tcp: "Modbus TCP", modbus_rtu: "Modbus RTU" };
const DEFAULT_STALE_AFTER_SEC = 60;

/** The selected device: identity and poll health, trend of one point, all points, recent events. */
export function DeviceDetail({ device, status, model, rules, log, now, timeZone, selectedPointId, trendRange, onSelectPoint, onTrendRangeChange, onOpenHistory }: {
  device: Device;
  status: DeviceStatus;
  model: AlarmModel;
  rules: Rule[];
  log: AlarmLogEntry[];
  now: number;
  timeZone: string;
  selectedPointId: string | null;
  trendRange: TrendRange;
  onSelectPoint: (pointId: string) => void;
  onTrendRangeChange: (range: TrendRange) => void;
  onOpenHistory: () => void;
}) {
  const points = useMemo(() => [...model.pointsById.values()].filter(point => point.deviceId === device.id), [model, device.id]);
  const limitsByPoint = useMemo(() => {
    const limits = new Map<string, ThresholdRule[]>();
    for (const rule of rules) {
      if (rule.type === "threshold" && rule.enabled) limits.set(rule.pointId, [...(limits.get(rule.pointId) ?? []), rule]);
    }
    return limits;
  }, [rules]);
  const violationByPoint = useMemo(() => {
    const violations = new Map<string, Severity>();
    for (const alarm of model.active) {
      if (alarm.point && alarm.point.deviceId === device.id && violations.get(alarm.point.id) !== "fault") {
        violations.set(alarm.point.id, alarm.event.severity);
      }
    }
    return violations;
  }, [model, device.id]);

  const staleRule = rules.find(rule => rule.type === "comms_stale" && rule.deviceId === device.id && rule.enabled);
  const staleAfterSec = staleRule?.type === "comms_stale" ? staleRule.staleAfterSec : DEFAULT_STALE_AFTER_SEC;
  const polledSecondsAgo = Math.max(0, Math.round((now - Date.parse(device.lastPollAt)) / 1000));
  const isPollStale = polledSecondsAgo > staleAfterSec;
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
            {PROTOCOL_LABEL[device.protocol]} · {device.address} · unit {device.unitId}
          </span>
        </div>
        {isPollStale ? (
          <span className="inline-flex items-center gap-1.5 text-sm">
            <SeverityIndicator severity="warning" showLabel={false} />
            <span className="text-alarm-warning">Poll stale: last {polledSecondsAgo} s ago</span>
          </span>
        ) : (
          <span className="text-sm tabular-nums text-muted-foreground">Polled {polledSecondsAgo} s ago</span>
        )}
      </header>

      {trendPoint ? (
        <TrendChart point={trendPoint} limits={limitsByPoint.get(trendPoint.id) ?? []} now={now} timeZone={timeZone}
          range={trendRange} onRangeChange={onTrendRangeChange} />
      ) : (
        <p className="text-sm text-muted-foreground">Select a numeric point below to see its trend.</p>
      )}

      <div>
        <h3 className="mb-1 text-sm font-medium">Points</h3>
        <PointsTable points={points} limitsByPoint={limitsByPoint} violationByPoint={violationByPoint}
          selectedPointId={trendPoint?.id ?? null} onSelectPoint={onSelectPoint} />
      </div>

      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <h3 className="text-sm font-medium">Events, last 6 h</h3>
          <button type="button" className="text-sm text-muted-foreground underline-offset-4 hover:underline" onClick={onOpenHistory}>
            Query full history
          </button>
        </div>
        <EventLog entries={deviceLog} timeZone={timeZone} />
      </div>
    </section>
  );
}
