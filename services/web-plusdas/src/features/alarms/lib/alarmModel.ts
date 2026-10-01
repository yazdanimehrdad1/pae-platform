import {
  describeConditionDraft,
  describeGroupDraft,
  flattenConditions,
  isBitOperator,
  operatorText,
  type ConditionPointOption,
} from "@/shared/components/conditions/conditionModel";
import { conditionFromWire, groupFromWire } from "@/shared/components/conditions/conditionWire";
import type { AlarmEvent, AlarmSnapshot, Device, DeviceStatus, Point, Rule } from "../types";
import { compareActiveAlarms } from "./alarmSort";
import { worstSeverity } from "./severity";

/** An alarm event with what the tables show next to it. */
export interface AlarmView {
  event: AlarmEvent;
  rule: Rule;
  /** null for a site-level alarm. */
  device: Device | null;
  /** The point a threshold rule watches; null for the other kinds. */
  point: Point | null;
}

export interface AlarmModel {
  devicesById: Map<string, Device>;
  pointsById: Map<string, Point>;
  rulesById: Map<string, Rule>;
  /** Active alarms in display order (only enabled rules have them). */
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

/** The point a threshold rule watches. */
export function watchedPointId(rule: Rule): string | null {
  return rule.rule?.kind === "threshold" ? String(rule.rule.condition.point_id) : null;
}

/** The device a rule is about: a threshold's point's device, the comms-stale device, or the one device all of a condition's points are on. */
export function ruleDeviceId(rule: Rule, pointsById: Map<string, Point>): string | null {
  const spec = rule.rule;
  if (!spec) return null;
  if (spec.kind === "comms_stale") return String(spec.device_id);
  const pointIds = spec.kind === "threshold"
    ? [String(spec.condition.point_id)]
    : flattenConditions(groupFromWire(spec.when)).map(condition => condition.pointId ?? "");
  const deviceIds = new Set(pointIds.map(pointId => pointsById.get(pointId)?.deviceId ?? null));
  return deviceIds.size === 1 ? [...deviceIds][0] : null;
}

export function buildAlarmModel(snapshot: AlarmSnapshot): AlarmModel {
  const devicesById = new Map(snapshot.devices.map(device => [device.id, device]));
  const pointsById = new Map(snapshot.points.map(point => [point.id, point]));
  const rulesById = new Map(snapshot.rules.map(rule => [rule.id, rule]));

  const views: AlarmView[] = snapshot.events.flatMap(event => {
    const rule = rulesById.get(event.ruleId);
    if (!rule) return [];
    const pointId = watchedPointId(rule);
    return [{
      event,
      rule,
      device: event.deviceId ? devicesById.get(event.deviceId) ?? null : null,
      point: pointId ? pointsById.get(pointId) ?? null : null,
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

  return {
    devicesById, pointsById, rulesById, active,
    recentlyCleared, deviceStatus, sortedDevices, devicesWithRecentEvents,
  };
}

/** A point value without its unit: an enum's state label, or a rounded number. */
export function formatPointNumber(point: Point, value: number | null = point.value): string {
  if (value === null) return "—";
  if (point.kind === "enum") return point.states?.find(state => state.value === value)?.label ?? String(value);
  if (point.kind === "bitfield") return `0x${value.toString(16).toUpperCase()}`;
  const decimals = Number.isInteger(value) ? 0 : Math.abs(value) < 100 ? 2 : 1;
  return value.toFixed(decimals);
}

/** A point value for display: an enum's state label, or a number with its unit. */
export function formatPointValue(point: Point, value: number | null = point.value): string {
  const number = formatPointNumber(point, value);
  return point.kind === "numeric" && point.unit && value !== null ? `${number} ${point.unit}` : number;
}

const delayText = (seconds: number) =>
  seconds > 0 ? ` for ${seconds >= 60 && seconds % 60 === 0 ? `${seconds / 60} min` : `${seconds} s`}` : "";

/** The limit side of a threshold ("> 85 °C", "≥ other point", "trip is set"), or the comms timeout. "—" for the other kinds. */
export function formatLimit(rule: Rule, pointsById: Map<string, ConditionPointOption>): string {
  const spec = rule.rule;
  if (spec?.kind === "comms_stale") return `> ${spec.stale_after_sec} s`;
  if (spec?.kind !== "threshold") return "—";
  const condition = conditionFromWire(spec.condition);
  const point = pointsById.get(condition.pointId ?? "");
  if (isBitOperator(condition.operator)) {
    const bitLabel = point?.bits?.find(bit => bit.bit === condition.bit)?.label ?? `bit ${condition.bit}`;
    return `${bitLabel} ${operatorText(condition.operator)}`;
  }
  const operand = condition.operand === "point"
    ? pointsById.get(condition.comparePointId ?? "")?.label ?? `point ${condition.comparePointId}`
    : point?.kind === "enum"
      ? point.states?.find(state => String(state.value) === condition.value)?.label ?? condition.value
      : `${condition.value}${point?.unit ? ` ${point.unit}` : ""}`;
  return `${operatorText(condition.operator, point?.kind)} ${operand}`;
}

/**
 * What the rule checks, in words: "BESS · state_of_charge < 20 % for 1 min",
 * "mock-device-2: no successful poll > 60 s", "(a and b) for 30 s"; a profile alarm's message.
 */
export function describeCondition(rule: Rule, pointsById: Map<string, ConditionPointOption>, devicesById: Map<string, Device>): string {
  const spec = rule.rule;
  if (!spec) return rule.message || "Defined in the site profile";
  switch (spec.kind) {
    case "comms_stale":
      return `${devicesById.get(String(spec.device_id))?.name ?? `Device ${spec.device_id}`}: no successful poll > ${spec.stale_after_sec} s`;
    case "threshold":
      return `${describeConditionDraft(conditionFromWire(spec.condition), pointsById)}${delayText(spec.delay_sec)}`;
    case "condition":
      return `${describeGroupDraft(groupFromWire(spec.when), pointsById)}${delayText(spec.delay_sec)}`;
  }
}

/** Kind label for the rules list. */
export const KIND_LABEL: Record<Rule["kind"], string> = {
  threshold: "Threshold",
  comms_stale: "Comms stale",
  condition: "Condition",
  profile: "Site profile",
};
