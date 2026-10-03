import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  newCondition,
  newGroup,
  newItemKey,
  type ConditionErrors,
  type ConditionGroupDraft,
  type ConditionOperator,
  type ConditionPointOption,
  type GroupItemDraft,
} from "./conditionModel";
import { ConditionRow } from "./ConditionRow";

/**
 * Conditions combined with ALL or ANY, plus nested groups down to `maxDepth` levels. A group keeps
 * at least one item. `errorsFor` returns the errors to show beside a condition (by item key).
 */
export function ConditionGroup({ group, onChange, points, operators, allowComparePoint = true, depth = 1, maxDepth = 2, errorsFor, onRemove, label = "Group" }: {
  group: ConditionGroupDraft;
  onChange: (group: ConditionGroupDraft) => void;
  points: ConditionPointOption[];
  operators?: ConditionOperator[];
  allowComparePoint?: boolean;
  depth?: number;
  maxDepth?: number;
  errorsFor?: (itemKey: string) => ConditionErrors | undefined;
  onRemove?: () => void;
  label?: string;
}) {
  const replaceItem = (key: string, next: GroupItemDraft) =>
    onChange({ ...group, items: group.items.map(item => (item.key === key ? next : item)) });
  const removeItem = (key: string) => onChange({ ...group, items: group.items.filter(item => item.key !== key) });
  const canRemoveItems = group.items.length > 1;

  return (
    <div role="group" aria-label={label} className={cn("space-y-2 rounded-md border border-border p-3", depth > 1 && "bg-muted/30")}>
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Match</span>
        <Select value={group.match} onValueChange={match => onChange({ ...group, match: match as ConditionGroupDraft["match"] })}>
          <SelectTrigger className="h-8 w-[5.5rem]" aria-label={`${label}: match`}><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">ALL</SelectItem>
            <SelectItem value="any">ANY</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-muted-foreground">of:</span>
        {onRemove && (
          <Button variant="ghost" size="icon" className="ml-auto h-7 w-7" aria-label={`Remove ${label.toLowerCase()}`} onClick={onRemove}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {group.items.map(item => item.type === "condition" ? (
        <ConditionRow
          key={item.key}
          condition={item.condition}
          onChange={condition => replaceItem(item.key, { ...item, condition })}
          points={points}
          operators={operators}
          allowComparePoint={allowComparePoint}
          errors={errorsFor?.(item.key)}
          onRemove={canRemoveItems ? () => removeItem(item.key) : undefined}
        />
      ) : (
        <ConditionGroup
          key={item.key}
          group={item.group}
          onChange={nested => replaceItem(item.key, { ...item, group: nested })}
          points={points}
          operators={operators}
          allowComparePoint={allowComparePoint}
          depth={depth + 1}
          maxDepth={maxDepth}
          errorsFor={errorsFor}
          onRemove={canRemoveItems ? () => removeItem(item.key) : undefined}
          label="Nested group"
        />
      ))}

      <div className="flex gap-2">
        <Button variant="outline" size="sm" className="h-7 gap-1 text-xs"
          onClick={() => onChange({ ...group, items: [...group.items, { type: "condition", key: newItemKey(), condition: newCondition() }] })}>
          <Plus className="h-3 w-3" />Condition
        </Button>
        {depth < maxDepth && (
          <Button variant="outline" size="sm" className="h-7 gap-1 text-xs"
            onClick={() => onChange({ ...group, items: [...group.items, { type: "group", key: newItemKey(), group: newGroup(group.match === "all" ? "any" : "all") }] })}>
            <Plus className="h-3 w-3" />Group
          </Button>
        )}
      </div>
    </div>
  );
}
