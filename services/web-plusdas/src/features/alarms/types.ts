// System alarms model (ISA-18.2 style). Mock data today (src/mocks/alarms/); the same shapes are
// what a live source must provide (see README.md next to this file).

export type Severity = 'fault' | 'warning';
export type Protocol = 'modbus_tcp' | 'modbus_rtu';
export type Quality = 'good' | 'stale' | 'bad';
export type DeviceType = 'transformer' | 'generator' | 'feeder' | 'protection' | 'switch' | 'bess';
export type Operator = '>' | '<' | '>=' | '<=' | '=' | '!=';

export interface Device {
  id: string;
  name: string;
  type: DeviceType;
  protocol: Protocol;
  /** IP for Modbus TCP, serial port for Modbus RTU. */
  address: string;
  unitId: number;
  lastPollAt: string;
}

export interface Point {
  id: string;
  /** null for a calculated (site-level) point. */
  deviceId: string | null;
  /** Modbus register, or null for a calculated point. */
  register: number | null;
  name: string;
  unit: string;
  kind: 'numeric' | 'discrete';
  /** Labels of a discrete point's values, e.g. { 0: 'open', 1: 'closed' }. */
  states?: Record<number, string>;
  value: number;
  quality: Quality;
  updatedAt: string;
}

export type NotificationChannel = 'mobile' | 'email';
export type NotificationSettings = Record<NotificationChannel, boolean>;

interface RuleBase {
  id: string;
  name: string;
  severity: Severity;
  message: string;
  enabled: boolean;
  /** Where to send a notification when this rule raises an alarm; any combination, or none. */
  notify: NotificationSettings;
}

/**
 * A real device point (backend-ot) a rule watches, kept on the rule so it can be shown without the
 * mock's points. Rules made in the builder have one; the demo rules on mock points don't.
 */
export interface RuleTarget {
  siteId: string;
  deviceName: string;
  pointName: string;
  unit: string | null;
  /** Labels of an enum point's values. */
  states?: Record<number, string>;
}

/** Raises when `point operator threshold` holds for delaySec; clears past threshold ± deadband. */
export interface ThresholdRule extends RuleBase {
  type: 'threshold';
  pointId: string;
  target?: RuleTarget;
  operator: Operator;
  threshold: number;
  delaySec: number;
  deadband: number;
}

/** Raises when a device has had no successful poll for more than staleAfterSec. */
export interface CommsStaleRule extends RuleBase {
  type: 'comms_stale';
  deviceId: string;
  staleAfterSec: number;
}

export type Rule = ThresholdRule | CommsStaleRule;

export interface AlarmEvent {
  id: string;
  ruleId: string;
  /** null when the rule's point is calculated (site-level). */
  deviceId: string | null;
  severity: Severity;
  raisedAt: string;
  clearedAt: string | null;
  valueAtRaise: number | null;
}

/** One line of the event log: every raise and clear. */
export interface AlarmLogEntry {
  id: string;
  eventId: string;
  ruleId: string;
  deviceId: string | null;
  kind: 'raised' | 'cleared';
  severity: Severity;
  at: string;
  message: string;
}

export interface Sample {
  t: number;
  v: number;
}

/** A successful or failed poll of a device. */
export interface PollSample {
  t: number;
  ok: boolean;
}

export type DeviceStatus = Severity | 'normal';

export interface HistoryFilter {
  deviceId?: string;
  severity?: Severity;
  ruleId?: string;
  from: number;
  to: number;
}
