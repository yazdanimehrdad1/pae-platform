import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { devicesApi, reportsApi } from "@/api";
import type {
  ReportRunCreateRequest,
  ReportRunRecord,
  ReportRunSummary,
  ReportScheduleCreateRequest,
  ReportScheduleUpdateRequest,
  ReportTemplateCreateRequest,
  ReportTemplateUpdateRequest,
} from "@/api/types/reports";
import { isPending } from "../lib/format";

// While a report is queued or generating, its list and its page poll until the worker is done.
const PENDING_POLL_MS = 2000;
// Otherwise the list and the schedules still refresh now and then: the server creates reports on
// its own (schedules), and there is no push channel to tell the page. React Query only polls while
// the page is open and its tab visible (refetchIntervalInBackground is off).
const IDLE_POLL_MS = 30_000;

export const reportKeys = {
  site: (siteId: string) => ["reports", siteId] as const,
  templates: (siteId: string) => ["reports", siteId, "templates"] as const,
  runs: (siteId: string) => ["reports", siteId, "runs"] as const,
  run: (siteId: string, runId: number) => ["reports", siteId, "run", runId] as const,
  template: (siteId: string, templateId: number) => ["reports", siteId, "template", templateId] as const,
  catalog: (siteId: string) => ["reports", siteId, "catalog"] as const,
  schedules: (siteId: string) => ["reports", siteId, "schedules"] as const,
};

export function useReportTemplates(siteId: string) {
  return useQuery({ queryKey: reportKeys.templates(siteId), queryFn: () => reportsApi.listTemplates(siteId) });
}

export function useReportRuns(siteId: string) {
  return useQuery({
    queryKey: reportKeys.runs(siteId),
    queryFn: () => reportsApi.listRuns(siteId),
    refetchInterval: query => (query.state.data?.some((run: ReportRunSummary) => isPending(run.status)) ? PENDING_POLL_MS : IDLE_POLL_MS),
  });
}

export function useReportRun(siteId: string, runId: number) {
  return useQuery({
    queryKey: reportKeys.run(siteId, runId),
    queryFn: () => reportsApi.getRun(siteId, runId),
    refetchInterval: query => (query.state.data && isPending((query.state.data as ReportRunRecord).status) ? PENDING_POLL_MS : false),
  });
}

export function useReportMutations(siteId: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: reportKeys.site(siteId) });
  return {
    generate: useMutation({
      mutationFn: (templateId: number) => reportsApi.requestRun(siteId, { template_id: templateId }),
      onSuccess: refresh,
    }),
    rerun: useMutation({ mutationFn: (runId: number) => reportsApi.rerun(siteId, runId), onSuccess: refresh }),
    deleteRun: useMutation({ mutationFn: (runId: number) => reportsApi.deleteRun(siteId, runId), onSuccess: refresh }),
    deleteAll: useMutation({ mutationFn: () => reportsApi.deleteRuns(siteId), onSuccess: refresh }),
  };
}

/** What the builder can offer on this site: its site functions and their numeric fields. */
export function useReportCatalog(siteId: string) {
  return useQuery({ queryKey: reportKeys.catalog(siteId), queryFn: () => reportsApi.getCatalog(siteId) });
}

export function useReportTemplate(siteId: string, templateId: number | null) {
  return useQuery({
    queryKey: reportKeys.template(siteId, templateId ?? 0),
    queryFn: () => reportsApi.getTemplate(siteId, templateId!),
    enabled: templateId !== null,
  });
}

/** The site's devices and points, shared with the asset tree and the alarm rules (same key). */
export function useSiteDevicePoints(siteId: string) {
  return useQuery({ queryKey: ["site-devices-with-points", siteId], queryFn: () => devicesApi.getBySiteWithPoints(siteId) });
}

export function useBuilderMutations(siteId: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: reportKeys.site(siteId) });
  return {
    requestRun: useMutation({ mutationFn: (payload: ReportRunCreateRequest) => reportsApi.requestRun(siteId, payload), onSuccess: refresh }),
    createTemplate: useMutation({ mutationFn: (payload: ReportTemplateCreateRequest) => reportsApi.createTemplate(siteId, payload), onSuccess: refresh }),
    updateTemplate: useMutation({
      mutationFn: ({ templateId, payload }: { templateId: number; payload: ReportTemplateUpdateRequest }) => reportsApi.updateTemplate(siteId, templateId, payload),
      onSuccess: refresh,
    }),
    deleteTemplate: useMutation({ mutationFn: (templateId: number) => reportsApi.deleteTemplate(siteId, templateId), onSuccess: refresh }),
  };
}

export function useReportSchedules(siteId: string) {
  // Refreshed like the reports list, so "Next report" moves on after a schedule fires.
  return useQuery({ queryKey: reportKeys.schedules(siteId), queryFn: () => reportsApi.listSchedules(siteId), refetchInterval: IDLE_POLL_MS });
}

export function useScheduleMutations(siteId: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: reportKeys.site(siteId) });
  return {
    create: useMutation({ mutationFn: (payload: ReportScheduleCreateRequest) => reportsApi.createSchedule(siteId, payload), onSuccess: refresh }),
    update: useMutation({
      mutationFn: ({ scheduleId, payload }: { scheduleId: number; payload: ReportScheduleUpdateRequest }) => reportsApi.updateSchedule(siteId, scheduleId, payload),
      onSuccess: refresh,
    }),
    remove: useMutation({ mutationFn: (scheduleId: number) => reportsApi.deleteSchedule(siteId, scheduleId), onSuccess: refresh }),
  };
}
