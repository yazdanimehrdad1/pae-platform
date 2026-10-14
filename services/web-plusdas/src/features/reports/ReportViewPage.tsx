import { Link, useParams } from "react-router-dom";
import { ArrowLeft, FileJson, Printer, RotateCw } from "lucide-react";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { TimeZoneToggle } from "@/shared/components/TimeZoneToggle";
import { useDisplayTimeZone } from "@/shared/hooks/useDisplayTimeZone";
import { toast } from "@/shared/hooks/use-toast";
import { ReportView } from "./components/ReportView";
import { RunStatusBadge } from "./components/RunStatusBadge";
import { useReportMutations, useReportRun } from "./hooks/useReports";
import { usePrintInLightTheme } from "./hooks/usePrintInLightTheme";
import { downloadFile, fileName } from "./lib/csv";

/** One report at /reports/:siteId/runs/:runId. The PDF exists only when the user exports it: the
 * browser's print dialog ("Save as PDF") prints the report alone, without the app around it. */
export default function ReportViewPage() {
  const { siteId = "", runId = "" } = useParams();
  const { data: run, isLoading, error } = useReportRun(siteId, Number(runId));
  const { rerun } = useReportMutations(siteId);
  usePrintInLightTheme();
  const { timeZone, display, setDisplay, siteTimeZone } = useDisplayTimeZone(run?.result?.timezone);

  const backLink = (
    <Button asChild variant="ghost" size="sm" className="gap-1.5 print:hidden">
      <Link to={`/reports?site=${siteId}`}><ArrowLeft aria-hidden className="h-4 w-4" />Reports</Link>
    </Button>
  );

  if (isLoading) return <div className="space-y-4 p-6">{backLink}<p className="text-sm text-muted-foreground">Loading report...</p></div>;
  if (error || !run) {
    return (
      <div className="space-y-4 p-6">
        {backLink}
        <p role="alert" className="text-sm text-destructive">{error ? getErrorMessage(error) : "Report not found"}</p>
      </div>
    );
  }

  const exportJson = () =>
    downloadFile(`${fileName(run.name, run.window_start.slice(0, 10))}.json`, JSON.stringify(run.result, null, 2), "application/json");
  const generateAgain = () =>
    rerun.mutate(run.id, {
      onSuccess: () => toast({ title: "Report queued", description: "The new report appears in the reports list when it is ready." }),
      onError: failure => toast({ title: "Could not generate it again", description: getErrorMessage(failure), variant: "destructive" }),
    });

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6 print:max-w-none print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        {backLink}
        {run.result && (
          <div className="flex flex-wrap items-center gap-2">
            <TimeZoneToggle siteTimeZone={siteTimeZone} display={display} onDisplayChange={setDisplay} />
            <Button size="sm" variant="outline" className="gap-1.5" onClick={generateAgain} disabled={rerun.isPending}>
              <RotateCw aria-hidden className="h-4 w-4" />Generate again
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5" onClick={exportJson}>
              <FileJson aria-hidden className="h-4 w-4" />JSON
            </Button>
            <Button size="sm" className="gap-1.5" onClick={() => window.print()}>
              <Printer aria-hidden className="h-4 w-4" />Export PDF
            </Button>
          </div>
        )}
      </div>
      {run.result ? (
        <ReportView name={run.name} snapshot={run.result} timeZone={timeZone} />
      ) : (
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">{run.name}</h1>
          <RunStatusBadge status={run.status} />
          {run.status === "failed" && <p className="text-sm text-muted-foreground">{run.error}</p>}
        </div>
      )}
    </div>
  );
}
