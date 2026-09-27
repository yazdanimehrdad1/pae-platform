import { OctagonAlert, TriangleAlert, type LucideIcon } from "lucide-react";
import type { Severity } from "../types";

// Every severity is shown with three cues (color, icon shape, word), so it reads in greyscale
// and for color-blind users. Normal has no entry: it is drawn in the default neutral colors.
export const SEVERITY: Record<Severity, {
  label: string;
  Icon: LucideIcon;
  rank: number;
  textClass: string;
  barClass: string;
  /** Left accent bar of a table row. */
  rowAccentClass: string;
}> = {
  fault: {
    label: "Fault",
    Icon: OctagonAlert,
    rank: 2,
    textClass: "text-alarm-fault",
    barClass: "bg-alarm-fault",
    rowAccentClass: "shadow-[inset_4px_0_0_0_hsl(var(--alarm-fault))]",
  },
  warning: {
    label: "Warning",
    Icon: TriangleAlert,
    rank: 1,
    textClass: "text-alarm-warning",
    barClass: "bg-alarm-warning",
    rowAccentClass: "shadow-[inset_4px_0_0_0_hsl(var(--alarm-warning))]",
  },
};

export function worstSeverity(severities: Iterable<Severity>): Severity | null {
  let worst: Severity | null = null;
  for (const severity of severities) {
    if (!worst || SEVERITY[severity].rank > SEVERITY[worst].rank) worst = severity;
  }
  return worst;
}
