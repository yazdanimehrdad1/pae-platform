import { Link } from "react-router-dom";
import { CalendarClock, RotateCw, Trash2 } from "lucide-react";
import type { ReportRunSummary } from "@/api/types/reports";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatReportTime, formatWindow, isPending } from "../lib/format";
import { RunStatusBadge } from "./RunStatusBadge";

/** The site's reports, newest first. A ready one opens; a failed one says why. */
export function RunList({ siteId, runs, isLoading, timeZone, onRerun, onDelete, onDeleteAll }: {
  siteId: string;
  runs: ReportRunSummary[];
  isLoading: boolean;
  timeZone: string;
  onRerun: (run: ReportRunSummary) => void;
  onDelete: (run: ReportRunSummary) => void;
  onDeleteAll: () => void;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1.5">
          <CardTitle>Reports</CardTitle>
          <CardDescription>Generated reports are stored, so they show the same numbers every time.</CardDescription>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button size="sm" variant="outline" className="gap-1.5" disabled={runs.length === 0}>
              <Trash2 aria-hidden className="h-4 w-4" />Delete all
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete all reports of this site?</AlertDialogTitle>
              <AlertDialogDescription>
                Every report of the site is deleted for everyone, including any being generated. Templates stay, so you can generate them again.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={onDeleteAll}>Delete all</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading reports...</p>
        ) : runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No reports yet. Generate one from a template.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Report</TableHead>
                <TableHead>Covers</TableHead>
                <TableHead>Requested</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right"><span className="sr-only">Actions</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map(run => (
                <TableRow key={run.id}>
                  <TableCell className="font-medium">
                    {run.status === "succeeded" ? (
                      <Link className="text-primary hover:underline" to={`/reports/${siteId}/runs/${run.id}`}>{run.name}</Link>
                    ) : run.name}
                    {run.trigger === "schedule" && (
                      <span className="ml-2 inline-flex items-center gap-1 text-xs font-normal text-muted-foreground">
                        <CalendarClock aria-hidden className="h-3.5 w-3.5" />Scheduled
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">{formatWindow(run.window_start, run.window_end, timeZone)}</TableCell>
                  <TableCell className="text-sm">{formatReportTime(run.requested_at, timeZone)}</TableCell>
                  <TableCell>
                    <RunStatusBadge status={run.status} />
                    {run.status === "failed" && run.error && <p className="mt-1 max-w-xs text-xs text-muted-foreground">{run.error}</p>}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="icon" variant="ghost" className="h-8 w-8" disabled={isPending(run.status)}
                        onClick={() => onRerun(run)} aria-label={`Generate ${run.name} again`} title="Generate again (same period, current data)"
                      >
                        <RotateCw aria-hidden className="h-4 w-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="icon" variant="ghost" className="h-8 w-8" aria-label={`Delete ${run.name}`} title="Delete">
                            <Trash2 aria-hidden className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete this report?</AlertDialogTitle>
                            <AlertDialogDescription>
                              "{run.name}" ({formatWindow(run.window_start, run.window_end, timeZone)}) is deleted for everyone. Its template stays.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => onDelete(run)}>Delete</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
