import { HideOnPhone } from "@/shared/components/HideOnPhone";
import { ListChecks, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SeverityIndicator } from "@/shared/components/SeverityIndicator";
import { SEVERITY, SEVERITIES_HIGH_FIRST } from "@/shared/lib/alarmSeverity";
import type { Severity } from "../types";

export function SummaryBar({ activeBySeverity, normalDevices, totalDevices, ruleCount, isBuilderOpen, onOpenRules, onToggleBuilder }: {
  /** Active alarms of each severity. */
  activeBySeverity: Record<Severity, number>;
  normalDevices: number;
  totalDevices: number;
  ruleCount: number;
  isBuilderOpen: boolean;
  onOpenRules: () => void;
  onToggleBuilder: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-md border border-border bg-card px-4 py-2.5 text-sm">
      {SEVERITIES_HIGH_FIRST.map(severity => {
        const count = activeBySeverity[severity];
        return (
          <span key={severity} className="inline-flex items-center gap-2">
            {count > 0 ? <SeverityIndicator severity={severity} showLabel={false} /> : null}
            <span className={count > 0 ? "font-semibold" : "text-muted-foreground"}>
              {count} active {SEVERITY[severity].label.toLowerCase()}
            </span>
          </span>
        );
      })}
      <span className="text-muted-foreground">{normalDevices} of {totalDevices} devices normal</span>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" className="gap-1" onClick={onOpenRules}>
          <ListChecks className="h-4 w-4" />Rules ({ruleCount})
        </Button>
        <HideOnPhone>
          <Button variant={isBuilderOpen ? "secondary" : "outline"} size="sm" className="gap-1" onClick={onToggleBuilder} aria-expanded={isBuilderOpen}>
            <Plus className="h-4 w-4" />New rule
          </Button>
        </HideOnPhone>
      </div>
    </div>
  );
}
