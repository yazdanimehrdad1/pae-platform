import { useQuery } from "@tanstack/react-query";
import { alarmsApi } from "@/api";
import type { ActiveAlarmsSummaryRecord, AlarmSeverity } from "@/api/types/alarms";
import { SEVERITY, SEVERITIES_HIGH_FIRST } from "@/shared/lib/alarmSeverity";

// backend-ot evaluates alarms about every poll interval; the alarms page polls at the same pace.
const ACTIVE_ALARMS_POLL_MS = 10_000;

/** Active alarms across every site, polled for app-wide indicators (the sidebar bell). */
export function useActiveAlarms() {
  return useQuery({
    queryKey: ["alarms", "active-summary"],
    queryFn: alarmsApi.getActiveSummary,
    refetchInterval: ACTIVE_ALARMS_POLL_MS,
    retry: false,
  });
}

/** How many events of this severity are active. */
export function activeCount(summary: ActiveAlarmsSummaryRecord, severity: AlarmSeverity): number {
  return { HIGH: summary.high_count, MEDIUM: summary.medium_count, LOW: summary.low_count }[severity];
}

/** The worst active severity (HIGH over MEDIUM over LOW); null when nothing is active. */
export function worstActiveSeverity(summary: ActiveAlarmsSummaryRecord | undefined): AlarmSeverity | null {
  if (!summary) return null;
  return SEVERITIES_HIGH_FIRST.find(severity => activeCount(summary, severity) > 0) ?? null;
}

/** "2 high, 1 low active" (only the non-zero parts); null when nothing is active. */
export function activeAlarmsText(summary: ActiveAlarmsSummaryRecord | undefined): string | null {
  if (!summary) return null;
  const parts = SEVERITIES_HIGH_FIRST
    .filter(severity => activeCount(summary, severity) > 0)
    .map(severity => `${activeCount(summary, severity)} ${SEVERITY[severity].label.toLowerCase()}`);
  return parts.length > 0 ? `${parts.join(", ")} active` : null;
}
