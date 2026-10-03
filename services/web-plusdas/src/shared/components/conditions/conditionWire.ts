import type { VirtualCondition, VirtualConditionGroupInput, VirtualConditionGroupOutput } from "@/api/types/devicePoints";
import {
  isBitOperator,
  newItemKey,
  type ConditionDraft,
  type ConditionGroupDraft,
  type GroupItemDraft,
} from "./conditionModel";

// The condition editor's drafts to and from backend-ot's condition models (VirtualCondition,
// VirtualConditionGroup), which virtual points and alarm rules share.

export function conditionFromWire(condition: VirtualCondition): ConditionDraft {
  return {
    pointId: String(condition.point_id),
    operator: condition.operator,
    operand: condition.compare_point_id != null ? "point" : "value",
    value: condition.value != null ? String(condition.value) : "",
    comparePointId: condition.compare_point_id != null ? String(condition.compare_point_id) : null,
    bit: condition.bit ?? null,
  };
}

export function groupFromWire(group: VirtualConditionGroupOutput): ConditionGroupDraft {
  return {
    match: group.match,
    items: group.items.map((item): GroupItemDraft => item.type === "group"
      ? { type: "group", key: newItemKey(), group: groupFromWire(item as VirtualConditionGroupOutput) }
      : { type: "condition", key: newItemKey(), condition: conditionFromWire(item as VirtualCondition) }),
  };
}

/** Only call it on a condition that validated. */
export function conditionToWire(condition: ConditionDraft): VirtualCondition {
  const bitTest = isBitOperator(condition.operator);
  const comparesPoint = !bitTest && condition.operand === "point";
  return {
    type: "condition",
    point_id: Number(condition.pointId),
    operator: condition.operator,
    value: bitTest || comparesPoint ? null : Number(condition.value),
    compare_point_id: comparesPoint ? Number(condition.comparePointId) : null,
    bit: bitTest ? condition.bit : null,
  };
}

/** Only call it on a group whose conditions validated. */
export function groupToWire(group: ConditionGroupDraft): VirtualConditionGroupInput {
  return {
    type: "group",
    match: group.match,
    items: group.items.map(item => item.type === "group" ? groupToWire(item.group) : conditionToWire(item.condition)),
  };
}
