// System alarms page model (ISA-18.2 style), built from backend-ot data in lib/pageData.ts:
// alarms and events from the alarms snapshot, devices and points from the site's devices, values
// from the latest readings. Ids are strings, as everywhere in the UI.

import type { AlarmKind, AlarmLogRecord, AlarmRuleRecord, AlarmSeverity, AlarmSource } from "@/api/types/alarms";
import type { DevicePointCategory } from "@/api/types/devicePoints";
import type { ConditionPointOption } from "@/shared/components/conditions/conditionModel";

export type Severity = AlarmSeverity;
export type DeviceStatus = Severity | "normal";

export interface Device {
  id: string;
  name: string;
  protocol: string;
  host: string;
  port: number;
  unitId: number;
  /** When the device's newest stored native reading was taken; null if it was never polled. */
  lastPollAt: string | null;
}

/** A device point with its latest stored value; also a condition picker option. */
export interface Point extends ConditionPointOption {
  deviceId: string;
  /** Modbus address; null for a standardized or virtual point. */
  register: number | null;
  category: DevicePointCategory;
  value: number | null;
  updatedAt: string | null;
}

export type NotificationChannel = "mobile" | "email";
export type NotificationSettings = Record<NotificationChannel, boolean>;

/** One alarm definition: a USER rule built in the UI, or a PROFILE alarm defined in the site's code. */
export interface Rule {
  id: string;
  name: string;
  source: AlarmSource;
  kind: AlarmKind;
  /** What a USER rule checks; null for a PROFILE alarm. */
  rule: AlarmRuleRecord | null;
  profileKey: string | null;
  severity: Severity;
  message: string;
  /** Evaluated and shown in Active alarms (at most MAX_ENABLED_ALARMS per site); a disabled rule is neither. */
  enabled: boolean;
  notify: NotificationSettings;
  createdAt: string;
  updatedAt: string;
}

export interface AlarmEvent {
  id: string;
  ruleId: string;
  /** null for a site-level alarm. */
  deviceId: string | null;
  severity: Severity;
  raisedAt: string;
  clearedAt: string | null;
  valueAtRaise: number | null;
  message: string;
}

/** One line of the event log: every raise and clear. */
export interface AlarmLogEntry {
  id: string;
  eventId: string;
  ruleId: string;
  deviceId: string | null;
  kind: AlarmLogRecord["kind"];
  severity: Severity;
  at: string;
  message: string;
}

export interface Sample {
  t: number;
  v: number;
}

export interface HistoryFilter {
  deviceId?: string;
  severity?: Severity;
  ruleId?: string;
  from: number;
  to: number;
}

/** Everything the page shows for "now". */
export interface AlarmSnapshot {
  siteId: string;
  /** Server time of the alarms snapshot (ms); durations are measured against it, not the browser clock. */
  now: number;
  devices: Device[];
  points: Point[];
  rules: Rule[];
  /** Active alarms plus those cleared within the recent window (6 h). */
  events: AlarmEvent[];
  /** Raise and clear entries within the recent window, newest first. */
  log: AlarmLogEntry[];
}
