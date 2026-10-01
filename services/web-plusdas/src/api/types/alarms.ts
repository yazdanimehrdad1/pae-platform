import type { components } from '@contracts/backend-ot';

type Schemas = components['schemas'];

// Wire types: generated from backend-ot's contract, never hand-written.
export type AlarmDefinitionRecord = Schemas['AlarmDefinitionResponse'];
export type AlarmDefinitionCreateRequest = Schemas['AlarmDefinitionCreateRequest'];
export type AlarmDefinitionUpdateRequest = Schemas['AlarmDefinitionUpdateRequest'];
export type AlarmEventRecord = Schemas['AlarmEventResponse'];
export type AlarmLogRecord = Schemas['AlarmLogEntry'];
export type AlarmSnapshotRecord = Schemas['AlarmSnapshotResponse'];
export type AlarmSeverity = AlarmDefinitionRecord['severity'];
export type AlarmSource = AlarmDefinitionRecord['source'];
export type AlarmKind = AlarmDefinitionRecord['kind'];
/** What a USER alarm checks, as stored (null for a PROFILE alarm). */
export type AlarmRuleRecord = NonNullable<AlarmDefinitionRecord['rule']>;
/** What a new or changed USER alarm checks. */
export type AlarmRuleInput = AlarmDefinitionCreateRequest['rule'];
export type ThresholdAlarmRule = Schemas['ThresholdAlarm'];
export type CommsStaleAlarmRule = Schemas['CommsStaleAlarm'];
export type ConditionAlarmRule = Schemas['ConditionAlarm-Output'];

// Arguments of alarmsApi.queryEvents (a client call signature, not a wire type).
export interface AlarmEventQuery {
  startTime: string;
  endTime: string;
  deviceId?: number;
  severity?: AlarmSeverity;
  definitionId?: number;
}

/**
 * How many alarms a site can have enabled; an enabled alarm is evaluated and shown in Active alarms
 * (backend-ot's MAX_ENABLED_ALARMS; it answers 409 past it).
 */
export const MAX_ENABLED_ALARMS = 20;
