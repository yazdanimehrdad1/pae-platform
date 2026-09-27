import { ListChecks, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SeverityIndicator } from "./SeverityIndicator";

export function SummaryBar({ faults, warnings, normalDevices, totalDevices, ruleCount, isBuilderOpen, onOpenRules, onToggleBuilder }: {
  faults: number;
  warnings: number;
  normalDevices: number;
  totalDevices: number;
  ruleCount: number;
  isBuilderOpen: boolean;
  onOpenRules: () => void;
  onToggleBuilder: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-md border border-border bg-card px-4 py-2.5 text-sm">
      <span className="inline-flex items-center gap-2">
        {faults > 0 ? <SeverityIndicator severity="fault" showLabel={false} /> : null}
        <span className={faults > 0 ? "font-semibold" : "text-muted-foreground"}>{faults} active {faults === 1 ? "fault" : "faults"}</span>
      </span>
      <span className="inline-flex items-center gap-2">
        {warnings > 0 ? <SeverityIndicator severity="warning" showLabel={false} /> : null}
        <span className={warnings > 0 ? "font-semibold" : "text-muted-foreground"}>{warnings} active {warnings === 1 ? "warning" : "warnings"}</span>
      </span>
      <span className="text-muted-foreground">{normalDevices} of {totalDevices} devices normal</span>
      <div className="ml-auto flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-1" onClick={onOpenRules}>
          <ListChecks className="h-4 w-4" />Rules ({ruleCount})
        </Button>
        <Button variant={isBuilderOpen ? "secondary" : "outline"} size="sm" className="gap-1" onClick={onToggleBuilder} aria-expanded={isBuilderOpen}>
          <Plus className="h-4 w-4" />New rule
        </Button>
      </div>
    </div>
  );
}
