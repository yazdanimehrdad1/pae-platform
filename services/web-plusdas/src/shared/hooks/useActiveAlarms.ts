import { useQuery } from "@tanstack/react-query";
import { alarmsApi } from "@/api";
import type { ActiveAlarmsSummaryRecord, AlarmSeverity } from "@/api/types/alarms";

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

/** The worst active severity: a fault wins over warnings; null when nothing is active. */
export function worstActiveSeverity(summary: ActiveAlarmsSummaryRecord | undefined): AlarmSeverity | null {
  if (!summary) return null;
  if (summary.fault_count > 0) return "fault";
  if (summary.warning_count > 0) return "warning";
  return null;
}

/** "2 faults, 1 warning active" (only the non-zero parts); null when nothing is active. */
export function activeAlarmsText(summary: ActiveAlarmsSummaryRecord | undefined): string | null {
  if (!summary) return null;
  const parts = [
    summary.fault_count > 0 ? `${summary.fault_count} fault${summary.fault_count === 1 ? "" : "s"}` : null,
    summary.warning_count > 0 ? `${summary.warning_count} warning${summary.warning_count === 1 ? "" : "s"}` : null,
  ].filter((part): part is string => part !== null);
  return parts.length > 0 ? `${parts.join(", ")} active` : null;
}
