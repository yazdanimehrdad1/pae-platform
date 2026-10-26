import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { sitesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ReportRunSummary, ReportScheduleRecord, ReportTemplateRecord } from "@/api/types/reports";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TimeZoneToggle } from "@/shared/components/TimeZoneToggle";
import { useDisplayTimeZone } from "@/shared/hooks/useDisplayTimeZone";
import { toast } from "@/shared/hooks/use-toast";
import { RunList } from "./components/RunList";
import { ScheduleDialog, type ScheduleDraft } from "./components/ScheduleDialog";
import { ScheduleList } from "./components/ScheduleList";
import { TemplateList } from "./components/TemplateList";
import { useReportMutations, useReportRuns, useReportSchedules, useReportTemplates, useScheduleMutations } from "./hooks/useReports";
import { describeCadence } from "./lib/cadence";

/** Report templates and generated reports of a site. The site is in the URL (?site=), so the
 * report page can link back to the same site. */
export default function ReportsPage() {
  const { data: sites = [], isLoading: areSitesLoading } = useQuery({ queryKey: ["sites"], queryFn: sitesApi.getAll });
  const [searchParams, setSearchParams] = useSearchParams();
  const siteId = searchParams.get("site") ?? "";
  useEffect(() => {
    if (sites.length > 0 && !sites.some(site => site.id === siteId)) {
      setSearchParams({ site: sites[0].id }, { replace: true });
    }
  }, [sites, siteId, setSearchParams]);
  const site = sites.find(candidate => candidate.id === siteId);
  const { timeZone, display, setDisplay, siteTimeZone } = useDisplayTimeZone(site?.timezone);

  return (
    <div className="space-y-6 p-4 md:p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Reports</h1>
          <p className="text-sm text-muted-foreground">Generate reports from templates and open the ones already generated.</p>
          <div className="mt-1"><TimeZoneToggle siteTimeZone={siteTimeZone} display={display} onDisplayChange={setDisplay} /></div>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          {site && (
            <Button asChild size="sm" className="gap-1.5">
              <Link to={`/reports/${site.id}/builder`}><Plus aria-hidden className="h-4 w-4" />New report</Link>
            </Button>
          )}
          <div className="w-full space-y-1 sm:w-56">
            <Label htmlFor="reports-site" className="text-xs text-muted-foreground">Site</Label>
            <Select value={siteId} onValueChange={value => setSearchParams({ site: value })}>
              <SelectTrigger id="reports-site" className="h-8 text-sm"><SelectValue placeholder="Choose a site" /></SelectTrigger>
              <SelectContent>{sites.map(option => <SelectItem key={option.id} value={option.id}>{option.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
      </header>
      {site ? (
        <SiteReports key={site.id} siteId={site.id} timeZone={timeZone} siteTimeZone={site.timezone} />
      ) : (
        <p className="text-sm text-muted-foreground">{areSitesLoading ? "Loading sites..." : "No sites yet."}</p>
      )}
    </div>
  );
}

/** The dialog's subject: a new schedule (for a template, or to choose one) or one to change. */
type ScheduleEditing = { schedule: ReportScheduleRecord | null; templateId: number | null } | null;

function SiteReports({ siteId, timeZone, siteTimeZone }: { siteId: string; timeZone: string; siteTimeZone: string }) {
  const templates = useReportTemplates(siteId);
  const runs = useReportRuns(siteId);
  const schedules = useReportSchedules(siteId);
  const { generate, rerun, deleteRun, deleteAll } = useReportMutations(siteId);
  const scheduleMutations = useScheduleMutations(siteId);
  const [editing, setEditing] = useState<ScheduleEditing>(null);

  const onError = (title: string) => (error: unknown) =>
    toast({ title, description: getErrorMessage(error), variant: "destructive" });

  const onGenerate = (template: ReportTemplateRecord) =>
    generate.mutate(template.id, {
      onSuccess: () => toast({ title: "Report queued", description: `"${template.name}" is being generated.` }),
      onError: onError(`Could not generate "${template.name}"`),
    });
  const onRerun = (run: ReportRunSummary) =>
    rerun.mutate(run.id, {
      onSuccess: () => toast({ title: "Report queued", description: `"${run.name}" is being generated again.` }),
      onError: onError(`Could not generate "${run.name}" again`),
    });
  const onDelete = (run: ReportRunSummary) =>
    deleteRun.mutate(run.id, { onError: onError(`Could not delete "${run.name}"`) });

  const onDeleteAll = () =>
    deleteAll.mutate(undefined, {
      onSuccess: ({ deleted }) => toast({ title: "Reports deleted", description: `${deleted} report${deleted === 1 ? "" : "s"} deleted. Templates stay.` }),
      onError: onError("Could not delete the reports"),
    });

  const onSaveSchedule = (draft: ScheduleDraft) => {
    const done = {
      onSuccess: (saved: ReportScheduleRecord) => {
        setEditing(null);
        toast({ title: "Schedule saved", description: `"${saved.template_name}": ${describeCadence(saved.cadence).toLowerCase()} (${saved.timezone}).` });
      },
      onError: onError("Could not save the schedule"),
    };
    if (editing?.schedule) {
      const { template_id: _templateId, ...changes } = draft;
      scheduleMutations.update.mutate({ scheduleId: editing.schedule.id, payload: changes }, done);
    } else {
      scheduleMutations.create.mutate(draft, done);
    }
  };
  const onToggleSchedule = (schedule: ReportScheduleRecord, enabled: boolean) =>
    scheduleMutations.update.mutate({ scheduleId: schedule.id, payload: { enabled } }, { onError: onError("Could not change the schedule") });
  const onDeleteSchedule = (schedule: ReportScheduleRecord) =>
    scheduleMutations.remove.mutate(schedule.id, { onError: onError("Could not delete the schedule") });

  const loadError = templates.error ?? runs.error ?? schedules.error;
  return (
    <div className="space-y-6">
      {loadError && <p role="alert" className="text-sm text-destructive">{getErrorMessage(loadError)}</p>}
      <TemplateList
        siteId={siteId}
        templates={templates.data ?? []}
        isLoading={templates.isLoading}
        generatingId={generate.isPending ? (generate.variables ?? null) : null}
        onGenerate={onGenerate}
        onSchedule={template => setEditing({ schedule: null, templateId: template.id })}
      />
      <ScheduleList
        schedules={schedules.data ?? []}
        isLoading={schedules.isLoading}
        timeZone={timeZone}
        canCreate={(templates.data ?? []).length > 0}
        onCreate={() => setEditing({ schedule: null, templateId: templates.data?.[0]?.id ?? null })}
        onEdit={schedule => setEditing({ schedule, templateId: schedule.template_id })}
        onToggle={onToggleSchedule}
        onDelete={onDeleteSchedule}
      />
      {editing && (
        <ScheduleDialog
          open
          onOpenChange={open => !open && setEditing(null)}
          schedule={editing.schedule}
          templateId={editing.templateId}
          templates={templates.data ?? []}
          timeZone={siteTimeZone}
          isSaving={scheduleMutations.create.isPending || scheduleMutations.update.isPending}
          onSave={onSaveSchedule}
        />
      )}
      <RunList
        siteId={siteId}
        runs={runs.data ?? []}
        isLoading={runs.isLoading}
        timeZone={timeZone}
        onRerun={onRerun}
        onDelete={onDelete}
        onDeleteAll={onDeleteAll}
      />
    </div>
  );
}
