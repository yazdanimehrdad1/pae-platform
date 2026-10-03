import { useId } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  isBitOperator,
  operatorsFor,
  operatorText,
  withPoint,
  type ConditionDraft,
  type ConditionErrors,
  type ConditionOperator,
  type ConditionPointOption,
} from "./conditionModel";
import { PointCombobox } from "./PointCombobox";

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <p id={id} role="alert" className="text-xs text-alarm-fault">{message}</p> : null;
}

/**
 * One condition: point, operator, then what fits the point — a number, an enum state, a bit, or
 * (when `allowComparePoint`) another point. Labels are visible with `showLabels`, otherwise
 * screen-reader only. `ids` pins field ids (errors use `<id>-error`).
 */
export function ConditionRow({ condition, onChange, points, operators, allowComparePoint = false, errors = {}, showLabels = false, labels = {}, ids = {}, onRemove, className }: {
  condition: ConditionDraft;
  onChange: (condition: ConditionDraft) => void;
  points: ConditionPointOption[];
  operators?: ConditionOperator[];
  allowComparePoint?: boolean;
  errors?: ConditionErrors;
  showLabels?: boolean;
  labels?: { point?: string; operator?: string; value?: string };
  ids?: { point?: string; operator?: string; value?: string };
  onRemove?: () => void;
  className?: string;
}) {
  const generatedId = useId();
  const pointId = ids.point ?? `${generatedId}-point`;
  const operatorId = ids.operator ?? `${generatedId}-operator`;
  const valueId = ids.value ?? `${generatedId}-value`;
  const point = points.find(option => option.id === condition.pointId);
  const availableOperators = operatorsFor(point?.kind, operators);
  const labelClass = showLabels ? "" : "sr-only";
  const valueLabel = `${labels.value ?? "Value"}${point?.unit && !isBitOperator(condition.operator) ? ` (${point.unit})` : ""}`;
  const set = (patch: Partial<ConditionDraft>) => onChange({ ...condition, ...patch });

  const renderOperand = () => {
    if (isBitOperator(condition.operator)) {
      return (
        <Select value={condition.bit === null ? "" : String(condition.bit)} onValueChange={bit => set({ bit: Number(bit) })}>
          <SelectTrigger id={valueId} aria-invalid={!!errors.value} aria-describedby={`${valueId}-error`}><SelectValue placeholder="Choose a bit" /></SelectTrigger>
          <SelectContent>
            {(point?.bits ?? []).map(definition => (
              <SelectItem key={definition.bit} value={String(definition.bit)}>{definition.bit} · {definition.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }
    if (condition.operand === "point") {
      return (
        <PointCombobox id={valueId} options={points.filter(option => option.id !== condition.pointId)} value={condition.comparePointId}
          onChange={comparePointId => set({ comparePointId })} placeholder="Choose a point to compare with"
          invalid={!!errors.value} describedBy={`${valueId}-error`} ariaLabel={labels.value ?? "Compare with point"} />
      );
    }
    if (point?.kind === "enum") {
      return (
        <Select value={condition.value} onValueChange={value => set({ value })}>
          <SelectTrigger id={valueId} aria-invalid={!!errors.value} aria-describedby={`${valueId}-error`}><SelectValue placeholder="Choose a state" /></SelectTrigger>
          <SelectContent>
            {(point.states ?? []).map(state => <SelectItem key={state.value} value={String(state.value)}>{state.label}</SelectItem>)}
          </SelectContent>
        </Select>
      );
    }
    return (
      <Input id={valueId} inputMode="decimal" value={condition.value} onChange={event => set({ value: event.target.value })}
        aria-invalid={!!errors.value} aria-describedby={`${valueId}-error`} />
    );
  };

  const canComparePoint = allowComparePoint && point?.kind !== "enum" && !isBitOperator(condition.operator);

  return (
    <div className={cn("grid grid-cols-1 items-start gap-2 md:grid-cols-[minmax(0,3fr)_minmax(0,1.2fr)_minmax(0,2fr)_auto]", className)} data-testid="condition-row">
      <div className="space-y-1">
        <Label id={`${pointId}-label`} className={labelClass}>{labels.point ?? "Point"}</Label>
        <PointCombobox id={pointId} options={points} value={condition.pointId} ariaLabelledBy={`${pointId}-label`}
          onChange={nextPointId => onChange(withPoint(condition, points.find(option => option.id === nextPointId), operators, point))}
          placeholder="Choose a point" invalid={!!errors.point} describedBy={`${pointId}-error`} />
        <FieldError id={`${pointId}-error`} message={errors.point} />
      </div>
      <div className="space-y-1">
        <Label htmlFor={operatorId} className={labelClass}>{labels.operator ?? "Operator"}</Label>
        <Select value={condition.operator}
          onValueChange={operator => {
            const next = operator as ConditionOperator;
            set({ operator: next, bit: isBitOperator(next) ? condition.bit ?? point?.bits?.[0]?.bit ?? null : null });
          }}>
          <SelectTrigger id={operatorId}><SelectValue /></SelectTrigger>
          <SelectContent>
            {availableOperators.map(operator => <SelectItem key={operator} value={operator}>{operatorText(operator, point?.kind)}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor={valueId} className={labelClass}>{isBitOperator(condition.operator) ? "Bit" : valueLabel}</Label>
        <div className="flex gap-2">
          {canComparePoint && (
            <Select value={condition.operand} onValueChange={operand => set({ operand: operand as ConditionDraft["operand"] })}>
              <SelectTrigger className="w-[6.5rem] shrink-0" aria-label="Compare with"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="value">value</SelectItem>
                <SelectItem value="point">point</SelectItem>
              </SelectContent>
            </Select>
          )}
          <div className="min-w-0 flex-1">{renderOperand()}</div>
        </div>
        <FieldError id={`${valueId}-error`} message={errors.value} />
      </div>
      {onRemove && (
        <Button variant="ghost" size="icon" className={cn("h-10 w-10", showLabels && "mt-6")} aria-label="Remove condition" onClick={onRemove}>
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
