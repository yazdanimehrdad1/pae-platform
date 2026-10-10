import type { PointSeverity } from "@/api/types/sites";
import { POINT_SEVERITY } from "../lib/pointSeverity";
import { useSiteHealth } from "../hooks/useSiteHealth";

const SEVERITY_COUNTS: { severity: PointSeverity; key: "high_count" | "medium_count" | "low_count" }[] = [
  { severity: "HIGH", key: "high_count" },
  { severity: "MEDIUM", key: "medium_count" },
  { severity: "LOW", key: "low_count" },
];

// The site's set ALARM points per severity, shown on the site bar whether it is open or not.
export function SiteHealthCounts({ siteId }: { siteId: string }) {
  const { data: health, isLoading, error } = useSiteHealth(siteId);

  if (isLoading) {
    return <span className="text-xs text-muted-foreground" role="status">Loading alarms…</span>;
  }
  if (error || !health) {
    return <span className="text-xs text-muted-foreground">Alarms unavailable</span>;
  }
  return (
    <div className="flex items-center gap-4" aria-label="Active alarms by severity">
      {SEVERITY_COUNTS.map(({ severity, key }) => {
        const { label, Icon, textClass } = POINT_SEVERITY[severity];
        return (
          <div key={severity} className="text-center">
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
