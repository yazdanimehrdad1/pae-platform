import type {
  ReportCatalogRecord,
  ReportRunCreateRequest,
  ReportRunQuery,
  ReportRunRecord,
  ReportRunSummary,
  ReportRunsDeleteResponse,
  ReportScheduleCreateRequest,
  ReportScheduleRecord,
  ReportScheduleUpdateRequest,
  ReportTemplateCreateRequest,
  ReportTemplateRecord,
  ReportTemplateUpdateRequest,
} from './types/reports';
import { client, request } from './client';

// A site's reports: templates (what a report contains) and runs (queued or generated reports).
// backend-ot generates a requested run in the background: it comes back 'queued', then turns
// 'succeeded' (with `result`, the stored report) or 'failed' (with `error`).
export const reportsApi = {
  /** What a report on this site can contain: block kinds, statistics, site functions. */
  getCatalog: (siteId: string): Promise<ReportCatalogRecord> =>
    client.get(`/reports/site/${siteId}/catalog`),

  listTemplates: (siteId: string): Promise<ReportTemplateRecord[]> =>
    client.get(`/reports/site/${siteId}/templates`),

  getTemplate: (siteId: string, templateId: number): Promise<ReportTemplateRecord> =>
    client.get(`/reports/site/${siteId}/templates/${templateId}`),

  createTemplate: (siteId: string, payload: ReportTemplateCreateRequest): Promise<ReportTemplateRecord> =>
    client.post(`/reports/site/${siteId}/templates`, payload),

  /** Omitted fields keep their value; a changed definition bumps the version. */
  updateTemplate: (siteId: string, templateId: number, payload: ReportTemplateUpdateRequest): Promise<ReportTemplateRecord> =>
    client.put(`/reports/site/${siteId}/templates/${templateId}`, payload),

  /** Its generated reports stay (with template_id null). Returns it as it was. */
  deleteTemplate: (siteId: string, templateId: number): Promise<ReportTemplateRecord> =>
    request<ReportTemplateRecord>(`/reports/site/${siteId}/templates/${templateId}`, { method: 'DELETE' }),

  /** Queue a report from a template or an inline definition; it comes back 'queued'. */
  requestRun: (siteId: string, payload: ReportRunCreateRequest): Promise<ReportRunRecord> =>
    client.post(`/reports/site/${siteId}/runs`, payload),

  /** Newest request first, without the report data. */
  listRuns: (siteId: string, query: ReportRunQuery = {}): Promise<ReportRunSummary[]> => {
    const params = new URLSearchParams();
    if (query.templateId !== undefined) params.set('template_id', String(query.templateId));
    if (query.status) params.set('status', query.status);
    if (query.scheduleId !== undefined) params.set('schedule_id', String(query.scheduleId));
    if (query.limit !== undefined) params.set('limit', String(query.limit));
    const search = params.toString();
    return client.get(`/reports/site/${siteId}/runs${search ? `?${search}` : ''}`);
  },

  /** The run with its stored report once it succeeded. */
  getRun: (siteId: string, runId: number): Promise<ReportRunRecord> =>
    client.get(`/reports/site/${siteId}/runs/${runId}`),

  /** Every report of the site (queued and generating ones too); templates stay. */
  deleteRuns: (siteId: string): Promise<ReportRunsDeleteResponse> =>
    request<ReportRunsDeleteResponse>(`/reports/site/${siteId}/runs`, { method: 'DELETE' }),

  deleteRun: (siteId: string, runId: number): Promise<ReportRunSummary> =>
    request<ReportRunSummary>(`/reports/site/${siteId}/runs/${runId}`, { method: 'DELETE' }),

  /** The site's schedules: each generates a template's report on a cadence (site time). */
  listSchedules: (siteId: string): Promise<ReportScheduleRecord[]> =>
    client.get(`/reports/site/${siteId}/schedules`),

  createSchedule: (siteId: string, payload: ReportScheduleCreateRequest): Promise<ReportScheduleRecord> =>
    client.post(`/reports/site/${siteId}/schedules`, payload),

  /** Omitted fields keep their value; null clears window_override, keep_last or keep_days. */
  updateSchedule: (siteId: string, scheduleId: number, payload: ReportScheduleUpdateRequest): Promise<ReportScheduleRecord> =>
    client.put(`/reports/site/${siteId}/schedules/${scheduleId}`, payload),

  /** Its reports stay. Returns it as it was. */
  deleteSchedule: (siteId: string, scheduleId: number): Promise<ReportScheduleRecord> =>
    request<ReportScheduleRecord>(`/reports/site/${siteId}/schedules/${scheduleId}`, { method: 'DELETE' }),

  /** Queue the same report again (same definition and window, current data). */
  rerun: (siteId: string, runId: number): Promise<ReportRunRecord> =>
    client.post(`/reports/site/${siteId}/runs/${runId}/rerun`, {}),
};
