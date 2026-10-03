import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { DISCRETE_MODES, isDiscreteModeId, type DiscreteModeId } from "./discreteModes";

export function DiscreteModeToggle({ mode, onChange }: { mode: DiscreteModeId; onChange: (mode: DiscreteModeId) => void }) {
  if (DISCRETE_MODES.length < 2) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">Status points</span>
      <ToggleGroup
        type="single"
        size="sm"
        variant="outline"
        value={mode}
        onValueChange={value => { if (isDiscreteModeId(value)) onChange(value); }}
        aria-label="How status points are drawn"
      >
        {DISCRETE_MODES.map(option => (
          <ToggleGroupItem key={option.id} value={option.id} className="h-7 px-2 text-xs">{option.label}</ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
