import type { DevicePoint, VirtualCalculationFunction, VirtualPointDefinitionInput } from "@/api/types/devicePoints";
import {
  describeGroupDraft,
  newGroup,
  newItemKey,
  validateCondition,
  type ConditionErrors,
  type ConditionGroupDraft,
  type ConditionPointOption,
} from "@/shared/components/conditions/conditionModel";
import { groupFromWire, groupToWire } from "@/shared/components/conditions/conditionWire";

// The virtual point form's model, and its conversion to and from backend-ot's definition.
// Limits mirror backend-ot's (schemas/api_models/virtual_points.py) so errors show before saving.

export type VirtualKind = "condition" | "calculation";

export const MAX_CASES = 10;
export const MAX_INPUTS = 20;
export const MAX_OUTPUT = 65535;

export const CALCULATION_FUNCTION_LABELS: Record<VirtualCalculationFunction, string> = {
  sum: "Sum",
  avg: "Average",
  min: "Minimum",
  max: "Maximum",
  difference: "Difference (A − B)",
  ratio: "Ratio (A ÷ B)",
};

export const isTwoInputFunction = (fn: VirtualCalculationFunction) => fn === "difference" || fn === "ratio";

export interface CaseDraft {
  key: string;
  output: string;
  label: string;
  group: ConditionGroupDraft;
}

export interface InputDraft {
  key: string;
  pointId: string | null;
}

export interface VirtualPointDraft {
  name: string;
  unit: string;
  kind: VirtualKind;
  cases: CaseDraft[];
  defaultOutput: string;
  defaultLabel: string;
  calcFunction: VirtualCalculationFunction;
  inputs: InputDraft[];
  scale: string;
  offset: string;
}

export const newCase = (output: number): CaseDraft => ({ key: newItemKey(), output: String(output), label: "", group: newGroup() });
export const newInput = (pointId: string | null = null): InputDraft => ({ key: newItemKey(), pointId });

export function emptyDraft(): VirtualPointDraft {
  return {
    name: "", unit: "", kind: "condition",
    cases: [newCase(1)], defaultOutput: "0", defaultLabel: "",
    calcFunction: "sum", inputs: [newInput(), newInput()], scale: "1", offset: "0",
  };
}

/** The form for an existing virtual point. */
export function draftFromPoint(point: DevicePoint): VirtualPointDraft {
  const draft = { ...emptyDraft(), name: point.name, unit: point.unit ?? "" };
  const definition = point.virtual_definition;
  if (!definition) return draft;
  if (definition.kind === "calculation") {
    return {
      ...draft, kind: "calculation", calcFunction: definition.function,
      inputs: definition.inputs.map(pointId => newInput(String(pointId))),
      scale: String(definition.scale ?? 1), offset: String(definition.offset ?? 0),
    };
  }
  return {
    ...draft, kind: "condition",
    cases: definition.cases.map(entry => ({
      key: newItemKey(), output: String(entry.output), label: entry.label ?? "", group: groupFromWire(entry.when),
    })),
    defaultOutput: String(definition.default_output ?? 0),
    defaultLabel: definition.default_label ?? "",
  };
}

/** The definition to send. Only call it on a draft that validated. */
export function toDefinition(draft: VirtualPointDraft): VirtualPointDefinitionInput {
  if (draft.kind === "calculation") {
    return {
      kind: "calculation", function: draft.calcFunction,
      inputs: draft.inputs.map(input => Number(input.pointId)),
      scale: Number(draft.scale), offset: Number(draft.offset),
    };
  }
  return {
    kind: "condition",
    cases: draft.cases.map(entry => ({ output: Number(entry.output), label: entry.label.trim() || null, when: groupToWire(entry.group) })),
    default_output: Number(draft.defaultOutput),
    default_label: draft.defaultLabel.trim() || null,
  };
}

export interface DraftErrors {
  name?: string;
  // Output error per case key, and for the "otherwise" output.
  caseOutputs: Record<string, string>;
  defaultOutput?: string;
  // Input error per input key.
  inputs: Record<string, string>;
  scale?: string;
  offset?: string;
  // Condition errors per condition item key.
  conditions: Record<string, ConditionErrors>;
}

function outputError(raw: string): string | undefined {
  if (raw.trim() === "") return "Required";
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0 || value > MAX_OUTPUT) return `A whole number 0-${MAX_OUTPUT}`;
  return undefined;
}

function numberError(raw: string): string | undefined {
  if (raw.trim() === "") return "Required";
  return Number.isFinite(Number(raw)) ? undefined : "Must be a number";
}

function collectConditionErrors(group: ConditionGroupDraft, into: Record<string, ConditionErrors>): void {
  for (const item of group.items) {
    if (item.type === "group") { collectConditionErrors(item.group, into); continue; }
    const errors = validateCondition(item.condition);
    if (Object.keys(errors).length > 0) into[item.key] = errors;
  }
}

export function validateDraft(draft: VirtualPointDraft): { errors: DraftErrors; isValid: boolean } {
  const errors: DraftErrors = { caseOutputs: {}, inputs: {}, conditions: {} };
  if (!draft.name.trim()) errors.name = "Required";

  if (draft.kind === "condition") {
    for (const entry of draft.cases) {
      const error = outputError(entry.output);
      if (error) errors.caseOutputs[entry.key] = error;
      collectConditionErrors(entry.group, errors.conditions);
    }
    errors.defaultOutput = outputError(draft.defaultOutput);
  } else {
    for (const input of draft.inputs) if (!input.pointId) errors.inputs[input.key] = "Choose a point";
    errors.scale = numberError(draft.scale);
    errors.offset = numberError(draft.offset);
  }

  const isValid = !errors.name && !errors.defaultOutput && !errors.scale && !errors.offset
    && [errors.caseOutputs, errors.inputs, errors.conditions].every(map => Object.keys(map).length === 0);
  return { errors, isValid };
}

/** Plain-text summary, one line per case (or one line for a calculation). */
export function describeDraft(draft: VirtualPointDraft, pointsById: Map<string, ConditionPointOption>): string[] {
  if (draft.kind === "calculation") {
    const names = draft.inputs.map(input => pointsById.get(input.pointId ?? "")?.label ?? "(no point)");
    const scale = Number(draft.scale) !== 1 ? ` × ${draft.scale}` : "";
    const offset = Number(draft.offset) !== 0 ? ` + ${draft.offset}` : "";
    return [`${CALCULATION_FUNCTION_LABELS[draft.calcFunction]} of ${names.join(", ")}${scale}${offset}`];
  }
  const outputText = (output: string, label: string) => (label.trim() ? `${output} "${label.trim()}"` : output);
  return [
    ...draft.cases.map((entry, index) =>
      `${index === 0 ? "If" : "Else if"} ${describeGroupDraft(entry.group, pointsById)} → ${outputText(entry.output, entry.label)}`),
    `Otherwise → ${outputText(draft.defaultOutput, draft.defaultLabel)}`,
  ];
}
