import { cn } from "@/lib/utils";
import { SEVERITY } from "../lib/severity";
import type { Severity } from "../types";

/** Severity as icon + word + color, so it reads in greyscale too. */
export function SeverityIndicator({ severity, showLabel = true, className }: {
  severity: Severity;
  showLabel?: boolean;
  className?: string;
}) {
  const { Icon, label, textClass } = SEVERITY[severity];
  return (
    <span className={cn("inline-flex items-center gap-1.5 font-medium", textClass, className)}>
      <Icon aria-hidden className="h-4 w-4 shrink-0" />
      {showLabel ? <span>{label}</span> : <span className="sr-only">{label}</span>}
    </span>
  );
}
