import { Info, OctagonAlert, TriangleAlert, type LucideIcon } from "lucide-react";
import type { AlarmSeverity as Severity } from "@/api/types/alarms";

// Every severity is shown with three cues (color, icon shape, word), so it reads in greyscale
// and for color-blind users. Normal has no entry: it is drawn in the default neutral colors.
// The scale is the same as a point's severity (HIGH, MEDIUM, LOW).
export const SEVERITY: Record<Severity, {
  label: string;
  Icon: LucideIcon;
  rank: number;
  textClass: string;
  barClass: string;
  /** Left accent bar of a table row. */
  rowAccentClass: string;
}> = {
  HIGH: {
    label: "High",
    Icon: OctagonAlert,
    rank: 3,
    textClass: "text-alarm-high",
    barClass: "bg-alarm-high",
    rowAccentClass: "shadow-[inset_4px_0_0_0_hsl(var(--alarm-high))]",
  },
  MEDIUM: {
    label: "Medium",
    Icon: TriangleAlert,
    rank: 2,
    textClass: "text-alarm-medium",
    barClass: "bg-alarm-medium",
    rowAccentClass: "shadow-[inset_4px_0_0_0_hsl(var(--alarm-medium))]",
  },
  LOW: {
    label: "Low",
    Icon: Info,
    rank: 1,
    textClass: "text-alarm-low",
    barClass: "bg-alarm-low",
    rowAccentClass: "shadow-[inset_4px_0_0_0_hsl(var(--alarm-low))]",
  },
};

/** Every severity, highest first. */
export const SEVERITIES_HIGH_FIRST: Severity[] = ["HIGH", "MEDIUM", "LOW"];

export function worstSeverity(severities: Iterable<Severity>): Severity | null {
  let worst: Severity | null = null;
  for (const severity of severities) {
    if (!worst || SEVERITY[severity].rank > SEVERITY[worst].rank) worst = severity;
  }
  return worst;
}
