import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { AXIS_SCALE_LABELS, isAxisScale, type AxisScale } from "../lib/axes";

/** How the chart's lines share vertical axes: one per unit (default), one per point, or one for all. */
export function AxisScaleToggle({ scale, onChange }: { scale: AxisScale; onChange: (scale: AxisScale) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">Axes</span>
      <ToggleGroup
        type="single"
        size="sm"
        variant="outline"
        value={scale}
        onValueChange={value => { if (isAxisScale(value)) onChange(value); }}
        aria-label="Vertical axes"
      >
        {(Object.keys(AXIS_SCALE_LABELS) as AxisScale[]).map(option => (
          <ToggleGroupItem key={option} value={option} className="h-7 px-2 text-xs">{AXIS_SCALE_LABELS[option]}</ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
