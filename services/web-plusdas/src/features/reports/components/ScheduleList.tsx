import { CalendarClock, Pencil, Plus, Trash2 } from "lucide-react";
import type { ReportScheduleRecord } from "@/api/types/reports";
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
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { describeCadence, describeRetention } from "../lib/cadence";
import { formatReportTime, windowLabel } from "../lib/format";

/** The site's schedules: when each generates which template, what it keeps, and when it next runs. */
export function ScheduleList({ schedules, isLoading, timeZone, canCreate, onCreate, onEdit, onToggle, onDelete }: {
  schedules: ReportScheduleRecord[];
  isLoading: boolean;
  timeZone: string;
  canCreate: boolean;
  onCreate: () => void;
  onEdit: (schedule: ReportScheduleRecord) => void;
  onToggle: (schedule: ReportScheduleRecord, enabled: boolean) => void;
  onDelete: (schedule: ReportScheduleRecord) => void;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1.5">
          <CardTitle>Schedules</CardTitle>
          <CardDescription>Generate a template's report on a cadence, on the site's clock.</CardDescription>
        </div>
        <Button size="sm" variant="outline" className="gap-1.5" disabled={!canCreate} onClick={onCreate} title={canCreate ? undefined : "Save a template first"}>
          <Plus aria-hidden className="h-4 w-4" />New schedule
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading schedules...</p>
        ) : schedules.length === 0 ? (
          <p className="text-sm text-muted-foreground">No schedules yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Template</TableHead>
                <TableHead>When ({schedules[0].timezone})</TableHead>
                <TableHead>Keeps</TableHead>
                <TableHead>Next report</TableHead>
                <TableHead>On</TableHead>
                <TableHead className="text-right"><span className="sr-only">Actions</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {schedules.map(schedule => (
                <TableRow key={schedule.id}>
                  <TableCell className="font-medium">
                    <span className="inline-flex items-center gap-1.5"><CalendarClock aria-hidden className="h-4 w-4 text-primary" />{schedule.template_name}</span>
                    {schedule.window_override && <p className="text-xs text-muted-foreground">Covers: {windowLabel(schedule.window_override)}</p>}
                  </TableCell>
                  <TableCell className="text-sm">{describeCadence(schedule.cadence)}</TableCell>
                  <TableCell className="text-sm">{describeRetention(schedule.keep_last, schedule.keep_days)}</TableCell>
                  <TableCell className="text-sm">
                    {schedule.enabled && schedule.next_run_at ? formatReportTime(schedule.next_run_at, timeZone) : "Off"}
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={schedule.enabled}
                      onCheckedChange={enabled => onToggle(schedule, enabled)}
                      aria-label={`${schedule.enabled ? "Turn off" : "Turn on"} the ${schedule.template_name} schedule`}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => onEdit(schedule)} aria-label={`Change the ${schedule.template_name} schedule`}>
                        <Pencil aria-hidden className="h-4 w-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="icon" variant="ghost" className="h-8 w-8" aria-label={`Delete the ${schedule.template_name} schedule`}>
                            <Trash2 aria-hidden className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete this schedule?</AlertDialogTitle>
                            <AlertDialogDescription>
                              "{schedule.template_name}" ({describeCadence(schedule.cadence)}) stops being generated. Its reports and the template stay.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => onDelete(schedule)}>Delete</AlertDialogAction>
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
