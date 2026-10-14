import type { PointSeverity } from "@/api/types/sites";
import { POINT_SEVERITY } from "../lib/pointSeverity";
import { useSiteHealth } from "../hooks/useSiteHealth";

const SEVERITY_COUNTS: { severity: PointSeverity; key: "high_count" | "medium_count" | "low_count" }[] = [
  { severity: "HIGH", key: "high_count" },
  { severity: "MEDIUM", key: "medium_count" },
  { severity: "LOW", key: "low_count" },
];

// Fixed width, left-aligned: the counts start at the same place on every site bar, whatever the
// numbers, and the loading/error text holds the same space.
const COLUMN_CLASS = "w-[13.5rem] shrink-0";

// The site's set ALARM points per severity, shown on the site bar whether it is open or not.
export function SiteHealthCounts({ siteId }: { siteId: string }) {
  const { data: health, isLoading, error } = useSiteHealth(siteId);

  if (isLoading) {
    return <span className={`${COLUMN_CLASS} text-xs text-muted-foreground`} role="status">Loading alarms…</span>;
  }
  if (error || !health) {
    return <span className={`${COLUMN_CLASS} text-xs text-muted-foreground`}>Alarms unavailable</span>;
  }
  return (
    <div className={`${COLUMN_CLASS} flex items-center justify-start gap-4`} aria-label="Active alarms by severity">
      {SEVERITY_COUNTS.map(({ severity, key }) => {
        const { label, Icon, textClass } = POINT_SEVERITY[severity];
        return (
          <div key={severity} className="w-16 text-left">
            <div className={`inline-flex items-center gap-1 data-metric text-sm ${textClass}`}>
              <Icon className="w-4 h-4" aria-hidden />
              {health[key] ?? 0}
            </div>
            <div className="data-label text-xs">{label}</div>
          </div>
        );
      })}
    </div>
  );
}
