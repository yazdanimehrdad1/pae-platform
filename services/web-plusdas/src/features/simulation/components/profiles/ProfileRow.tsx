import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ProfileChoice } from "../../lib/siteEdits";

// One load's or PV's profile choice: the scenario it follows and its scale.
export function ProfileRow({
  label,
  badge,
  choice,
  scenarios,
  disabled,
  onChange,
}: {
  label: string;
  badge?: ReactNode;
  choice: ProfileChoice;
  scenarios: string[];
  disabled?: boolean;
  onChange: (choice: ProfileChoice) => void;
}) {
  return (
    <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_14rem_7rem]">
      <div className="pb-2 space-y-1">
        <p className="text-sm text-foreground">{label}</p>
        {badge}
      </div>
      <div className="space-y-1">
        <Label>Scenario</Label>
        <Select value={choice.scenario} disabled={disabled} onValueChange={(scenario) => onChange({ ...choice, scenario })}>
          <SelectTrigger aria-label={`${label} scenario`}>
            <SelectValue placeholder="Choose a scenario" />
          </SelectTrigger>
          <SelectContent>
            {scenarios.map((scenario) => (
              <SelectItem key={scenario} value={scenario}>
                {scenario}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label>Scale</Label>
        <Input
          type="number"
          min={0}
          step={0.1}
          value={choice.scale}
          disabled={disabled}
          aria-label={`${label} scale`}
          onChange={(event) => onChange({ ...choice, scale: Number(event.target.value) })}
        />
      </div>
    </div>
  );
}
