import type { ComparisonOperator, ConditionPointOption } from "@/shared/components/conditions/conditionModel";
import type { Device, Operator, Point } from "../types";

// The alarm rule builder uses the shared condition editor; these map the alarm model onto it.

const CALCULATED_GROUP = "Calculated (site)";

export function toConditionPointOptions(points: Point[], devicesById: Map<string, Device>): ConditionPointOption[] {
  return points.map(point => {
    const deviceName = point.deviceId ? devicesById.get(point.deviceId)?.name ?? point.deviceId : null;
    const states = point.kind === "discrete" && point.states
      ? Object.entries(point.states).map(([value, label]) => ({ value: Number(value), label })).sort((left, right) => left.value - right.value)
      : undefined;
    return {
      id: point.id,
      name: point.name,
      label: `${deviceName ?? "Site (calculated)"} · ${point.name}`,
      group: deviceName ?? CALCULATED_GROUP,
      kind: states ? "enum" : "numeric",
      unit: point.unit,
      states,
      hint: point.register === null ? "calc" : String(point.register),
    };
  });
}

export const ALARM_OPERATORS: ComparisonOperator[] = [">", "<", ">=", "<=", "==", "!="];

export const toConditionOperator = (operator: Operator): ComparisonOperator => (operator === "=" ? "==" : operator);

export const toAlarmOperator = (operator: ComparisonOperator): Operator => (operator === "==" ? "=" : operator);
