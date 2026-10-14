import type { ReportWindow } from "@/api/types/reports";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { windowLabel } from "../../lib/format";
import { fromZonedInput, toZonedInput } from "@/shared/lib/zonedTime";

type WindowKind = ReportWindow["kind"];
type RollingDuration = Extract<ReportWindow, { kind: "rolling" }>["duration"];
type CalendarPeriod = Extract<ReportWindow, { kind: "calendar" }>["period"];

const KIND_LABELS: Record<WindowKind, string> = {
  calendar: "Calendar period (site time)",
  rolling: "Up to when it is generated",
  fixed: "Custom range",
};
const DURATIONS: RollingDuration[] = ["1H", "6H", "12H", "1D", "2D", "3D", "1W", "1M", "3M"];
const PERIODS: CalendarPeriod[] = ["day", "week", "month"];
const OFFSETS = [0, -1, -2, -3, -4, -5, -6, -7, -12];
const HOUR_MS = 3_600_000;

function defaultWindow(kind: WindowKind): ReportWindow {
  if (kind === "rolling") return { kind, duration: "1D" };
  if (kind === "calendar") return { kind, period: "day", offset: -1 };
  const end = Math.floor(Date.now() / HOUR_MS) * HOUR_MS;
  return { kind, start_time: new Date(end - 24 * HOUR_MS).toISOString(), end_time: new Date(end).toISOString() };
}

/** The period a report covers. A calendar period is a whole local day, week or month; a custom
 * range is typed in the site's time zone. */
export function WindowEditor({ window, timeZone, problems, onChange }: {
  window: ReportWindow;
  timeZone: string;
  problems: string[];
  onChange: (window: ReportWindow) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="window-kind">Period</Label>
          <Select value={window.kind} onValueChange={kind => onChange(defaultWindow(kind as WindowKind))}>
            <SelectTrigger id="window-kind"><SelectValue /></SelectTrigger>
            <SelectContent>
              {(Object.keys(KIND_LABELS) as WindowKind[]).map(kind => <SelectItem key={kind} value={kind}>{KIND_LABELS[kind]}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {window.kind === "rolling" && (
          <div className="space-y-1">
            <Label htmlFor="window-duration">Length</Label>
            <Select value={window.duration} onValueChange={duration => onChange({ ...window, duration: duration as RollingDuration })}>
              <SelectTrigger id="window-duration"><SelectValue /></SelectTrigger>
              <SelectContent>
                {DURATIONS.map(duration => <SelectItem key={duration} value={duration}>{windowLabel({ kind: "rolling", duration })}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
        {window.kind === "calendar" && (
          <>
            <div className="space-y-1">
              <Label htmlFor="window-period">Unit</Label>
              <Select value={window.period} onValueChange={period => onChange({ ...window, period: period as CalendarPeriod })}>
                <SelectTrigger id="window-period"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PERIODS.map(period => <SelectItem key={period} value={period}>{period[0].toUpperCase() + period.slice(1)}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="window-offset">Which</Label>
              <Select value={String(window.offset ?? -1)} onValueChange={offset => onChange({ ...window, offset: Number(offset) })}>
                <SelectTrigger id="window-offset"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {OFFSETS.map(offset => (
                    <SelectItem key={offset} value={String(offset)}>{windowLabel({ kind: "calendar", period: window.period, offset })}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </>
        )}
        {window.kind === "fixed" && (
          <>
            <div className="space-y-1">
              <Label htmlFor="window-start">From ({timeZone})</Label>
              <Input
                id="window-start" type="datetime-local" value={toZonedInput(window.start_time, timeZone)}
                onChange={event => event.target.value && onChange({ ...window, start_time: fromZonedInput(event.target.value, timeZone) })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="window-end">To ({timeZone})</Label>
              <Input
                id="window-end" type="datetime-local" value={toZonedInput(window.end_time, timeZone)}
                onChange={event => event.target.value && onChange({ ...window, end_time: fromZonedInput(event.target.value, timeZone) })}
              />
            </div>
          </>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        {window.kind === "fixed" ? "At most 92 days." : "Worked out when the report is generated, in the site's time zone."}
      </p>
      {problems.map(problem => <p key={problem} role="alert" className="text-sm text-destructive">{problem}</p>)}
    </div>
  );
}
