import type { AlarmEvent } from "../types";
import { SEVERITY } from "./severity";

/** Active alarm order: faults before warnings, then longest active first. */
export function compareActiveAlarms(a: AlarmEvent, b: AlarmEvent): number {
  const severityFirst = SEVERITY[b.severity].rank - SEVERITY[a.severity].rank;
  if (severityFirst !== 0) return severityFirst;
  return Date.parse(a.raisedAt) - Date.parse(b.raisedAt);
}
