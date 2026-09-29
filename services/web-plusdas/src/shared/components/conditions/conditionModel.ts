// The condition editor's model, shared by the alarm rule builder and virtual points. It is UI-only:
// each feature maps its own points into ConditionPointOption and converts drafts to its wire shape.

export type ConditionPointKind = "numeric" | "enum" | "bitfield";

export interface ConditionPointOption {
  id: string;
  name: string;
  // Shown on the picker button and in summaries, e.g. "mock-device-2 · battery_state".
  label: string;
  // Picker heading, e.g. the device name.
  group: string;
  kind: ConditionPointKind;
  unit?: string | null;
  // Enum states in value order.
  states?: Array<{ value: number; label: string }>;
  // Labelled bits in bit order.
  bits?: Array<{ bit: number; label: string }>;
  // Right-aligned extra text in the picker, e.g. the register.
  hint?: string;
}

export type ComparisonOperator = ">" | "<" | ">=" | "<=" | "==" | "!=";
export type BitOperator = "bit_set" | "bit_clear";
export type ConditionOperator = ComparisonOperator | BitOperator;

export const COMPARISON_OPERATORS: ComparisonOperator[] = [">", "<", ">=", "<=", "==", "!="];
export const BIT_OPERATORS: BitOperator[] = ["bit_set", "bit_clear"];

const OPERATOR_SYMBOL: Record<ConditionOperator, string> = {
  ">": ">", "<": "<", ">=": "≥", "<=": "≤", "==": "=", "!=": "≠", bit_set: "is set", bit_clear: "is clear",
};

export const isBitOperator = (operator: ConditionOperator): operator is BitOperator =>
  (BIT_OPERATORS as ConditionOperator[]).includes(operator);

/** How an operator reads for a point: "≥", "is" / "is not" for an enum, "is set" for a bit. */
export function operatorText(operator: ConditionOperator, kind?: ConditionPointKind): string {
  if (kind === "enum" && operator === "==") return "is";
  if (kind === "enum" && operator === "!=") return "is not";
  return OPERATOR_SYMBOL[operator];
}

/** Operators that make sense for a point kind, limited to `allowed` when given. */
export function operatorsFor(kind: ConditionPointKind | undefined, allowed?: ConditionOperator[]): ConditionOperator[] {
  const forKind: ConditionOperator[] =
    kind === "enum" ? ["==", "!="] : kind === "bitfield" ? [...BIT_OPERATORS, ...COMPARISON_OPERATORS] : COMPARISON_OPERATORS;
  return allowed ? forKind.filter(operator => allowed.includes(operator)) : forKind;
}

export interface ConditionDraft {
  pointId: string | null;
  operator: ConditionOperator;
  // Compare against a typed value or another point.
  operand: "value" | "point";
  // Raw text of the value input (or the chosen enum state), validated by the owner.
  value: string;
  comparePointId: string | null;
  bit: number | null;
}

export type GroupItemDraft =
  | { type: "condition"; key: string; condition: ConditionDraft }
  | { type: "group"; key: string; group: ConditionGroupDraft };

export interface ConditionGroupDraft {
  match: "all" | "any";
  items: GroupItemDraft[];
}

let nextKey = 0;
export const newItemKey = () => `item-${++nextKey}`;

export function newCondition(pointId: string | null = null): ConditionDraft {
  return { pointId, operator: ">", operand: "value", value: "", comparePointId: null, bit: null };
}

export function newGroup(match: "all" | "any" = "all"): ConditionGroupDraft {
  return { match, items: [{ type: "condition", key: newItemKey(), condition: newCondition() }] };
}

/**
 * A condition moved onto another point: keeps the operator while the point kind stays the same
 * (a fresh condition counts as numeric), otherwise takes the new kind's first operator, e.g. a
 * bit test for a bitfield. Resets the value for an enum and the bit for a bit test.
 */
export function withPoint(
  condition: ConditionDraft,
  point: ConditionPointOption | undefined,
  allowed?: ConditionOperator[],
  previous?: ConditionPointOption,
): ConditionDraft {
  const operators = operatorsFor(point?.kind, allowed);
  const sameKind = (previous?.kind ?? "numeric") === (point?.kind ?? "numeric");
  const operator = sameKind && operators.includes(condition.operator) ? condition.operator : operators[0] ?? ">";
  const bit = isBitOperator(operator) ? point?.bits?.[0]?.bit ?? null : null;
  const value = point?.kind === "enum" ? String(point.states?.[0]?.value ?? "") : condition.value;
  return { ...condition, pointId: point?.id ?? null, operator, bit, value, operand: point?.kind === "enum" ? "value" : condition.operand };
}

export interface ConditionErrors {
  point?: string;
  value?: string;
}

/** What's missing or invalid in one condition; empty when it's complete. */
export function validateCondition(condition: ConditionDraft): ConditionErrors {
  const errors: ConditionErrors = {};
  if (!condition.pointId) errors.point = "Choose a point";
  if (isBitOperator(condition.operator)) {
    if (condition.bit === null) errors.value = "Choose a bit";
  } else if (condition.operand === "point") {
    if (!condition.comparePointId) errors.value = "Choose a point";
  } else if (condition.value.trim() === "") {
    errors.value = "Required";
  } else if (!Number.isFinite(Number(condition.value))) {
    errors.value = "Must be a number";
  }
  return errors;
}

/** Every condition in a group, nested groups included. */
export function flattenConditions(group: ConditionGroupDraft): ConditionDraft[] {
  return group.items.flatMap(item => (item.type === "condition" ? [item.condition] : flattenConditions(item.group)));
}

/** "battery_state is fault", "state_of_charge ≥ 20", "flags · bms_err is set". */
export function describeConditionDraft(condition: ConditionDraft, pointsById: Map<string, ConditionPointOption>): string {
  const point = condition.pointId ? pointsById.get(condition.pointId) : undefined;
  const name = point?.label ?? "(no point)";
  if (isBitOperator(condition.operator)) {
    const bitLabel = point?.bits?.find(definition => definition.bit === condition.bit)?.label ?? `bit ${condition.bit}`;
    return `${name} · ${bitLabel} ${operatorText(condition.operator)}`;
  }
  const operand = condition.operand === "point"
    ? pointsById.get(condition.comparePointId ?? "")?.label ?? "(no point)"
    : point?.kind === "enum"
      ? point.states?.find(state => String(state.value) === condition.value)?.label ?? condition.value
      : `${condition.value}${point?.unit ? ` ${point.unit}` : ""}`;
  return `${name} ${operatorText(condition.operator, point?.kind)} ${operand}`;
}

export function describeGroupDraft(group: ConditionGroupDraft, pointsById: Map<string, ConditionPointOption>): string {
  const parts = group.items.map(item =>
    item.type === "condition" ? describeConditionDraft(item.condition, pointsById) : `(${describeGroupDraft(item.group, pointsById)})`,
  );
  return parts.join(group.match === "all" ? " and " : " or ");
}
