import { operatorText } from "@/shared/components/conditions/conditionModel";
import type { AlarmSnapshot } from "../data/AlarmDataSource";
import type { AlarmEvent, Device, DeviceStatus, Point, Rule } from "../types";
import { compareActiveAlarms } from "./alarmSort";
import { toConditionOperator } from "./conditionPoints";
import { worstSeverity } from "./severity";

/** An alarm event with what the tables show next to it. */
export interface AlarmView {
  event: AlarmEvent;
  rule: Rule;
  /** null for a calculated (site-level) rule. */
  device: Device | null;
  /** The rule's point; null for a comms-stale rule. */
  point: Point | null;
}

export interface AlarmModel {
  devicesById: Map<string, Device>;
  pointsById: Map<string, Point>;
  rulesById: Map<string, Rule>;
  /** Active alarms in display order. */
  active: AlarmView[];
  /** Alarms cleared within the recent window, newest first. */
  recentlyCleared: AlarmView[];
  deviceStatus: Map<string, DeviceStatus>;
  /** Devices worst first (fault, warning, normal), then by name. */
  sortedDevices: Device[];
  /** Devices without an active alarm that had one in the recent window. */
  devicesWithRecentEvents: Set<string>;
}

const STATUS_ORDER: Record<DeviceStatus, number> = { fault: 0, warning: 1, normal: 2 };

export function buildAlarmModel(snapshot: AlarmSnapshot): AlarmModel {
  const devicesById = new Map(snapshot.devices.map(device => [device.id, device]));
  const pointsById = new Map(snapshot.points.map(point => [point.id, point]));
  const rulesById = new Map(snapshot.rules.map(rule => [rule.id, rule]));

  const views: AlarmView[] = snapshot.events.flatMap(event => {
    const rule = rulesById.get(event.ruleId);
    if (!rule) return [];
    return [{
      event,
      rule,
      device: event.deviceId ? devicesById.get(event.deviceId) ?? null : null,
      point: rule.type === "threshold" ? pointsById.get(rule.pointId) ?? null : null,
    }];
  });

  const active = views.filter(view => view.event.clearedAt === null)
    .sort((a, b) => compareActiveAlarms(a.event, b.event));
  const recentlyCleared = views.filter(view => view.event.clearedAt !== null)
    .sort((a, b) => Date.parse(b.event.clearedAt!) - Date.parse(a.event.clearedAt!));

  const deviceStatus = new Map<string, DeviceStatus>(snapshot.devices.map(device => [
    device.id,
    worstSeverity(active.filter(view => view.event.deviceId === device.id).map(view => view.event.severity)) ?? "normal",
  ]));
  const devicesWithRecentEvents = new Set(
    recentlyCleared.map(view => view.event.deviceId).filter((id): id is string => id !== null && deviceStatus.get(id) === "normal"),
  );

  const statusRank = (device: Device) => STATUS_ORDER[deviceStatus.get(device.id) ?? "normal"];
  const sortedDevices = [...snapshot.devices].sort((a, b) => statusRank(a) - statusRank(b) || a.name.localeCompare(b.name));

  return { devicesById, pointsById, rulesById, active, recentlyCleared, deviceStatus, sortedDevices, devicesWithRecentEvents };
}


/** A point value without its unit: a discrete point's state label, or a rounded number. */
export function formatPointNumber(point: Point, value: number = point.value): string {
  if (point.kind === "discrete") return point.states?.[value] ?? String(value);
  const decimals = point.unit === "MW" || point.unit === "Hz" ? 2 : Math.abs(value) < 100 ? 1 : 0;
  return value.toFixed(decimals);
}

/** A point value for display: a discrete point's state label, or a number with its unit. */
export function formatPointValue(point: Point, value: number = point.value): string {
  const number = formatPointNumber(point, value);
  return point.kind === "numeric" && point.unit ? `${number} ${point.unit}` : number;
}

export function formatLimit(rule: Rule, point: Point | null): string {
  if (rule.type === "comms_stale") return `${rule.staleAfterSec} s`;
  if (point?.kind === "discrete") return `${operatorText(toConditionOperator(rule.operator))} ${point.states?.[rule.threshold] ?? rule.threshold}`;
  return `${operatorText(toConditionOperator(rule.operator))} ${rule.threshold}${point?.unit ? ` ${point.unit}` : ""}`;
}

/** "Phase B current > 600 A", "Top-oil temperature > 85 °C for 5 min", "No successful poll > 60 s". */
export function describeCondition(rule: Rule, point: Point | null): string {
  if (rule.type === "comms_stale") return `Comms lost: no successful poll > ${rule.staleAfterSec} s`;
  const delay = rule.delaySec > 0 ? ` for ${rule.delaySec >= 60 ? `${rule.delaySec / 60} min` : `${rule.delaySec} s`}` : "";
  return `${point?.name ?? rule.pointId} ${formatLimit(rule, point)}${delay}`;
}
