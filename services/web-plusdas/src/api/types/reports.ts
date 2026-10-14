import type { components } from '@contracts/backend-ot';

type Schemas = components['schemas'];

// Wire types: generated from backend-ot's contract, never hand-written.
export type ReportCatalogRecord = Schemas['ReportCatalogResponse'];
export type ReportSiteFunction = Schemas['ReportSiteFunction'];
export type ReportDefinition = Schemas['ReportDefinition'];
export type ReportWindow = ReportDefinition['window'];
export type ReportBlock = ReportDefinition['blocks'][number];
export type ReportTemplateRecord = Schemas['ReportTemplateResponse'];
export type ReportTemplateCreateRequest = Schemas['ReportTemplateCreateRequest'];
export type ReportTemplateUpdateRequest = Schemas['ReportTemplateUpdateRequest'];
export type ReportRunCreateRequest = Schemas['ReportRunCreateRequest'];
export type ReportRunSummary = Schemas['ReportRunSummary'];
export type ReportRunRecord = Schemas['ReportRunResponse'];
export type ReportRunStatus = ReportRunSummary['status'];
export type ReportRunsDeleteResponse = Schemas['ReportRunsDeleteResponse'];
export type ReportTextVariables = Schemas['ReportTextVariables'];
export type ReportTextVariable = Schemas['ReportTextVariable'];
export type ReportScheduleRecord = Schemas['ReportScheduleResponse'];
export type ReportScheduleCreateRequest = Schemas['ReportScheduleCreateRequest'];
export type ReportScheduleUpdateRequest = Schemas['ReportScheduleUpdateRequest'];
export type ReportCadence = ReportScheduleRecord['cadence'];
export type ReportSnapshot = Schemas['ReportSnapshot'];
export type ReportBlockResult = NonNullable<ReportSnapshot['blocks']>[number];
export type TextBlockResult = Schemas['TextResult'];
export type KpiBlockResult = Schemas['KpiResult'];
export type KpiValue = Schemas['KpiValue'];
export type ChartBlockResult = Schemas['ChartResult'];
export type PointTimeseries = Schemas['PointTimeseries'];
export type PointStatsTableResult = Schemas['PointStatsTableResult'];
export type PointStatsRow = Schemas['PointStatsRow'];
export type PointStat = Schemas['PointStatKpi']['stat'];
export type AlarmEventsTableResult = Schemas['AlarmEventsTableResult'];
export type AlarmEventRow = Schemas['AlarmEventRow'];

// Arguments of reportsApi.listRuns (a client call signature, not a wire type).
export interface ReportRunQuery {
  templateId?: number;
  status?: ReportRunStatus;
  scheduleId?: number;
  limit?: number;
}
