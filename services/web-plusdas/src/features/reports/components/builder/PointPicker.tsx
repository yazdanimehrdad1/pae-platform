import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PointCombobox } from "@/shared/components/conditions/PointCombobox";
import type { ConditionPointOption } from "@/shared/components/conditions/conditionModel";
import { UNSET_POINT } from "../../lib/draft";

/** One point (UNSET_POINT while none is chosen). */
export function PointPicker({ options, pointId, onChange, ariaLabel }: {
  options: ConditionPointOption[];
  pointId: number;
  onChange: (pointId: number) => void;
  ariaLabel: string;
}) {
  return (
    <PointCombobox
      options={options}
      value={pointId === UNSET_POINT ? null : String(pointId)}
      onChange={value => onChange(Number(value))}
      ariaLabel={ariaLabel}
      invalid={pointId === UNSET_POINT}
      className="w-full"
    />
  );
}

/** An ordered list of points, each removable, up to `max`. */
export function PointListPicker({ options, pointIds, max, onChange, label }: {
  options: ConditionPointOption[];
  pointIds: number[];
  max: number;
  onChange: (pointIds: number[]) => void;
  label: string;
}) {
  return (
    <div className="space-y-2">
      {pointIds.map((pointId, index) => (
        <div key={index} className="flex items-center gap-2">
          <PointPicker
            options={options}
            pointId={pointId}
            ariaLabel={`${label} ${index + 1}`}
            onChange={chosen => onChange(pointIds.map((current, position) => (position === index ? chosen : current)))}
          />
          <Button
            type="button" size="icon" variant="ghost" className="h-8 w-8 shrink-0" aria-label={`Remove ${label.toLowerCase()} ${index + 1}`}
            onClick={() => onChange(pointIds.filter((_, position) => position !== index))}
          >
            <X aria-hidden className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button" size="sm" variant="outline" className="gap-1.5" disabled={pointIds.length >= max}
        onClick={() => onChange([...pointIds, UNSET_POINT])}
      >
        <Plus aria-hidden className="h-3.5 w-3.5" />Add {label.toLowerCase()}
      </Button>
      {pointIds.length >= max && <p className="text-xs text-muted-foreground">At most {max}.</p>}
    </div>
  );
}
