import type {
  AlarmDefinitionCreateRequest,
  AlarmDefinitionRecord,
  AlarmDefinitionUpdateRequest,
  AlarmEventQuery,
  AlarmEventRecord,
  AlarmSnapshotRecord,
} from './types/alarms';
import { client, request } from './client';

// System alarms of a site (backend-ot evaluates them; the UI shows and configures them).
export const alarmsApi = {
  /** Server time, the site's alarms, active events plus those cleared in the last 6 h, and their log. */
  getSnapshot: (siteId: string): Promise<AlarmSnapshotRecord> =>
    client.get(`/alarms/site/${siteId}/snapshot`),

  /** Events overlapping the range, newest raise first. */
  queryEvents: (siteId: string, query: AlarmEventQuery): Promise<AlarmEventRecord[]> => {
    const params = new URLSearchParams({ start_time: query.startTime, end_time: query.endTime });
    if (query.deviceId !== undefined) params.set('device_id', String(query.deviceId));
    if (query.severity) params.set('severity', query.severity);
    if (query.definitionId !== undefined) params.set('definition_id', String(query.definitionId));
    return client.get(`/alarms/site/${siteId}/events?${params}`);
  },

  create: (siteId: string, payload: AlarmDefinitionCreateRequest): Promise<AlarmDefinitionRecord> =>
    client.post(`/alarms/site/${siteId}/definitions`, payload),

  /** Omitted fields keep their value. A profile alarm takes only enabled and notify_*. */
  update: (siteId: string, alarmId: number, payload: AlarmDefinitionUpdateRequest): Promise<AlarmDefinitionRecord> =>
    client.put(`/alarms/site/${siteId}/definitions/${alarmId}`, payload),

  /** Permanently deletes a user alarm and its events. Returns it as it was. */
  remove: (siteId: string, alarmId: number): Promise<AlarmDefinitionRecord> =>
    request<AlarmDefinitionRecord>(`/alarms/site/${siteId}/definitions/${alarmId}`, { method: 'DELETE' }),
};
