import type { AlarmEvent, AlarmLogEntry, Device, HistoryFilter, Point, Rule, Sample } from "../types";

export interface SiteInfo {
  name: string;
  /** IANA zone every timestamp is shown in, e.g. "America/Denver". */
  timeZone: string;
}

/** Everything the page shows for "now": current state first, recent history for the event logs. */
export interface AlarmSnapshot {
  site: SiteInfo;
  /** Server time of the snapshot (ms); durations are measured against it, not the browser clock. */
  now: number;
  devices: Device[];
  points: Point[];
  rules: Rule[];
  /** Active alarms plus those cleared within the recent window (6 h). */
  events: AlarmEvent[];
  /** Raise and clear entries within the recent window, newest first. */
  log: AlarmLogEntry[];
}

/**
 * The page's only data dependency. Today src/mocks/alarms implements it in memory; a live
 * implementation maps the same calls onto backend-ot (REST for queries and commands, and a
 * WebSocket or SSE channel that calls the subscribers on every change). See ../README.md.
 */
export interface AlarmDataSource {
  getSnapshot(): Promise<AlarmSnapshot>;
  /** Samples of one numeric point, oldest first. */
  getSeries(pointId: string, from: number, to: number): Promise<Sample[]>;
  /** Alarm events over any range, for the history query. */
  queryEvents(filter: HistoryFilter): Promise<AlarmEvent[]>;
  /** Creates the rule, or replaces the one with the same id (e.g. to enable it or turn its notifications on). */
  saveRule(rule: Rule): Promise<void>;
  /** Calls onChange whenever the snapshot changes (new poll, raise, clear, rule edit). */
  subscribe(onChange: () => void): () => void;
}
