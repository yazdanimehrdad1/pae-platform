import { CircleDashed, Info, OctagonAlert, TriangleAlert, type LucideIcon } from "lucide-react";
import type { PointSeverity } from "@/api/types/sites";

interface SeverityStyle {
  label: string;
  Icon: LucideIcon;
  textClass: string;
}

// Severity of a device's ALARM-class point (site health). Every level is shown with three cues
// (color, icon shape, word), so it reads in greyscale and for color-blind users.
export const POINT_SEVERITY: Record<PointSeverity, SeverityStyle> = {
  HIGH: { label: "High", Icon: OctagonAlert, textClass: "text-alarm-fault" },
  MEDIUM: { label: "Medium", Icon: TriangleAlert, textClass: "text-alarm-warning" },
  LOW: { label: "Low", Icon: Info, textClass: "text-muted-foreground" },
};

// An ALARM point that declares no severity.
export const UNRATED: SeverityStyle = { label: "Unrated", Icon: CircleDashed, textClass: "text-muted-foreground" };

export function pointSeverityStyle(severity: PointSeverity | null | undefined): SeverityStyle {
  return severity ? POINT_SEVERITY[severity] : UNRATED;
}
