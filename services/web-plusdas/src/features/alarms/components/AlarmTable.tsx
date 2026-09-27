import type { KeyboardEvent } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { AlarmView } from "../lib/alarmModel";
import { describeCondition, formatLimit, formatPointValue } from "../lib/alarmModel";
import { SEVERITY } from "../lib/severity";
import { formatDuration, formatSiteTime } from "../lib/siteTime";
import type { NotificationSettings, Rule } from "../types";
import { NotificationToggles } from "./NotificationToggles";
import { SeverityIndicator } from "./SeverityIndicator";

function currentValue(view: AlarmView, now: number): string {
  if (view.rule.type === "comms_stale") {
    return view.device ? `${Math.round((now - Date.parse(view.device.lastPollAt)) / 1000)} s` : "—";
  }
  return view.point ? formatPointValue(view.point) : "—";
}

/** Active rule violations only (not devices), faults first, then longest active. */
export function AlarmTable({ alarms, now, timeZone, selectedEventId, lastClearedAt, clearedCount, onSelect, onChangeNotify, onOpenHistory }: {
  alarms: AlarmView[];
  now: number;
  timeZone: string;
  selectedEventId: string | null;
  lastClearedAt: string | null;
  clearedCount: number;
  onSelect: (alarm: AlarmView) => void;
  /** Sets the alarm's rule notification channels (applies to all its future raises). */
  onChangeNotify: (rule: Rule, notify: NotificationSettings) => void;
  onOpenHistory: () => void;
}) {
  const onRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, alarm: AlarmView) => {
    if (event.target !== event.currentTarget) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(alarm);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const sibling = event.key === "ArrowDown" ? event.currentTarget.nextElementSibling : event.currentTarget.previousElementSibling;
      (sibling as HTMLElement | null)?.focus();
    }
  };

  return (
    <section aria-labelledby="active-alarms-heading" className="rounded-md border border-border bg-card">
      <div className="border-b border-border px-4 py-2">
        <h2 id="active-alarms-heading" className="text-sm font-semibold">Active alarms</h2>
      </div>

      {alarms.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-muted-foreground">
          No active alarms{lastClearedAt && <> · last cleared {formatSiteTime(lastClearedAt, timeZone, { withDate: true })}</>}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">Severity</TableHead>
              <TableHead>Condition</TableHead>
              <TableHead>Source</TableHead>
              <TableHead className="text-right">Value / limit</TableHead>
              <TableHead className="text-right">Active for</TableHead>
              <TableHead className="w-44" title="Where this alarm's rule sends notifications">Notifications</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {alarms.map(alarm => {
              const { event, rule, device, point } = alarm;
              return (
                <TableRow
                  key={event.id}
                  data-event-id={event.id}
                  tabIndex={0}
                  aria-selected={selectedEventId === event.id}
                  onClick={() => onSelect(alarm)}
                  onKeyDown={keyEvent => onRowKeyDown(keyEvent, alarm)}
                  className={cn(
                    SEVERITY[event.severity].rowAccentClass,
                    "cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                    selectedEventId === event.id && "bg-muted",
                    !device && "cursor-default",
                  )}
                >
                  <TableCell className="pl-5"><SeverityIndicator severity={event.severity} /></TableCell>
                  <TableCell className="font-medium">{describeCondition(rule, point)}</TableCell>
                  <TableCell className={cn(!device && "text-muted-foreground")}>{device ? device.name : "Site (calculated)"}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    <span className={SEVERITY[event.severity].textClass}>{currentValue(alarm, now)}</span>
                    <span className="text-muted-foreground"> / {formatLimit(rule, point)}</span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatDuration(now - Date.parse(event.raisedAt))}</TableCell>
                  <TableCell onClick={clickEvent => clickEvent.stopPropagation()} onKeyDown={keyEvent => keyEvent.stopPropagation()}>
                    <NotificationToggles value={rule.notify} onChange={notify => onChangeNotify(rule, notify)}
                      label={`Notifications for ${rule.name}`} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <div className="border-t border-border px-4 py-2 text-sm">
        <button type="button" className="text-muted-foreground underline-offset-4 hover:underline" onClick={onOpenHistory}>
          {clearedCount} cleared in last 6 h
        </button>
      </div>
    </section>
  );
}
