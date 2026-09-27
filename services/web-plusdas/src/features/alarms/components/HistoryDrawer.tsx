import { useMemo, useState } from "react";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useAlarmHistory } from "../hooks/useAlarmsData";
import { describeCondition, type AlarmModel } from "../lib/alarmModel";
import { SEVERITY } from "../lib/severity";
import { formatDuration, formatSiteTime } from "../lib/siteTime";
import type { AlarmEvent, Device, HistoryFilter, Severity } from "../types";
import { SeverityIndicator } from "./SeverityIndicator";

const RANGES = [
  { value: "6h", label: "Last 6 h", ms: 6 * 3_600_000 },
  { value: "24h", label: "Last 24 h", ms: 24 * 3_600_000 },
  { value: "7d", label: "Last 7 d", ms: 7 * 24 * 3_600_000 },
];
const CORRELATION_WINDOW_MS = 60_000;
const ALL = "all";
const SITE_LANE = "site";

export function HistoryDrawer({ open, onOpenChange, model, devices, now, timeZone, initialDeviceId }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model: AlarmModel;
  devices: Device[];
  now: number;
  timeZone: string;
  initialDeviceId: string | null;
}) {
  const [deviceId, setDeviceId] = useState<string>(initialDeviceId ?? ALL);
  const [severity, setSeverity] = useState<string>(ALL);
  const [ruleId, setRuleId] = useState<string>(ALL);
  const [range, setRange] = useState("24h");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [showCorrelated, setShowCorrelated] = useState(false);

  // Whole minutes, so the 5 s refresh doesn't re-key the query every tick.
  const to = Math.ceil(now / 60_000) * 60_000;
  const from = to - RANGES.find(option => option.value === range)!.ms;
  const filter: HistoryFilter = {
    from, to,
    ...(deviceId !== ALL ? { deviceId } : {}),
    ...(severity !== ALL ? { severity: severity as Severity } : {}),
    ...(ruleId !== ALL ? { ruleId } : {}),
  };
  const { data: events = [], isLoading } = useAlarmHistory(filter, open);

  const sortedEvents = useMemo(() => [...events].sort((a, b) => Date.parse(b.raisedAt) - Date.parse(a.raisedAt)), [events]);
  const lanes = useMemo(() => {
    const laneIds = [...new Set(events.map(event => event.deviceId ?? SITE_LANE))];
    const order = devices.map(device => device.id);
    return laneIds.sort((a, b) => (a === SITE_LANE ? 1 : b === SITE_LANE ? -1 : order.indexOf(a) - order.indexOf(b)));
  }, [events, devices]);

  const selectedEvent = events.find(event => event.id === selectedEventId) ?? null;
  const isCorrelated = (event: AlarmEvent) =>
    !selectedEvent || Math.abs(Date.parse(event.raisedAt) - Date.parse(selectedEvent.raisedAt)) <= CORRELATION_WINDOW_MS;
  const dimmed = (event: AlarmEvent) => showCorrelated && selectedEvent !== null && !isCorrelated(event);

  const laneName = (lane: string) => (lane === SITE_LANE ? "Site (calculated)" : model.devicesById.get(lane)?.name ?? lane);
  const conditionOf = (event: AlarmEvent) => {
    const rule = model.rulesById.get(event.ruleId);
    if (!rule) return event.ruleId;
    return describeCondition(rule, rule.type === "threshold" ? model.pointsById.get(rule.pointId) ?? null : null);
  };
  const position = (event: AlarmEvent) => {
    const start = Math.max(Date.parse(event.raisedAt), from);
    const end = Math.min(event.clearedAt ? Date.parse(event.clearedAt) : now, to);
    return { left: `${((start - from) / (to - from)) * 100}%`, width: `max(3px, ${((end - start) / (to - from)) * 100}%)` };
  };
  const ticks = Array.from({ length: 5 }, (_, index) => from + ((to - from) * index) / 4);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-5xl">
        <SheetHeader>
          <SheetTitle>Alarm history</SheetTitle>
          <SheetDescription>Events at their true start and duration. Times in {timeZone}.</SheetDescription>
        </SheetHeader>

        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <FilterSelect id="history-device" label="Device" value={deviceId} onChange={setDeviceId}
            options={[{ value: ALL, label: "All devices" }, ...devices.map(device => ({ value: device.id, label: device.name }))]} />
          <FilterSelect id="history-severity" label="Severity" value={severity} onChange={setSeverity}
            options={[{ value: ALL, label: "All" }, { value: "fault", label: "Fault" }, { value: "warning", label: "Warning" }]} />
          <FilterSelect id="history-rule" label="Rule" value={ruleId} onChange={setRuleId}
            options={[{ value: ALL, label: "All rules" }, ...[...model.rulesById.values()].map(rule => ({ value: rule.id, label: rule.name }))]} />
          <FilterSelect id="history-range" label="Time range" value={range} onChange={setRange} options={RANGES} />
        </div>

        <div className="mt-4 flex items-center gap-2">
          <Switch id="history-correlated" checked={showCorrelated} onCheckedChange={setShowCorrelated} />
          <Label htmlFor="history-correlated" className="font-normal">Show events within ±1 min of the selected event</Label>
          {showCorrelated && !selectedEvent && <span className="text-xs text-muted-foreground">(select an event)</span>}
        </div>

        <div className="mt-4 space-y-1" aria-busy={isLoading}>
          {lanes.length === 0 && !isLoading && <p className="text-sm text-muted-foreground">No events match these filters.</p>}
          {lanes.map(lane => (
            <div key={lane} className="flex items-center gap-2">
              <span className="w-36 shrink-0 truncate text-xs text-muted-foreground">{laneName(lane)}</span>
              <div className="relative h-6 flex-1 rounded-sm bg-muted/40">
                {events.filter(event => (event.deviceId ?? SITE_LANE) === lane).map(event => (
                  <button
                    key={event.id}
                    type="button"
                    style={position(event)}
                    onClick={() => setSelectedEventId(event.id === selectedEventId ? null : event.id)}
                    aria-pressed={event.id === selectedEventId}
                    aria-label={`${SEVERITY[event.severity].label}: ${conditionOf(event)}, ${formatSiteTime(event.raisedAt, timeZone, { withDate: true })}`}
                    title={`${SEVERITY[event.severity].label} · ${conditionOf(event)} · ${formatSiteTime(event.raisedAt, timeZone, { withDate: true })}`}
                    className={cn(
                      "absolute top-1 h-4 rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring",
                      SEVERITY[event.severity].barClass,
                      event.id === selectedEventId && "ring-2 ring-foreground ring-offset-1 ring-offset-background",
                      dimmed(event) && "opacity-20",
                    )}
                  />
                ))}
              </div>
            </div>
          ))}
          {lanes.length > 0 && (
            <div className="ml-[9.5rem] flex justify-between text-[11px] tabular-nums text-muted-foreground">
              {ticks.map(tick => <span key={tick}>{formatSiteTime(tick, timeZone, { withDate: true }).replace(/ \S+$/, "")}</span>)}
            </div>
          )}
        </div>

        <Table className="mt-4">
          <TableHeader>
            <TableRow>
              <TableHead>Raised</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Condition</TableHead>
              <TableHead className="text-right">Duration</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedEvents.map(event => (
              <TableRow key={event.id} tabIndex={0} aria-selected={event.id === selectedEventId}
                onClick={() => setSelectedEventId(event.id)}
                onKeyDown={keyEvent => { if (keyEvent.key === "Enter") setSelectedEventId(event.id); }}
                className={cn("cursor-pointer", event.id === selectedEventId && "bg-muted", dimmed(event) && "opacity-40")}>
                <TableCell className="tabular-nums">{formatSiteTime(event.raisedAt, timeZone, { withDate: true })}</TableCell>
                <TableCell>{laneName(event.deviceId ?? SITE_LANE)}</TableCell>
                <TableCell><SeverityIndicator severity={event.severity} /></TableCell>
                <TableCell>{conditionOf(event)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {event.clearedAt ? formatDuration(Date.parse(event.clearedAt) - Date.parse(event.raisedAt)) : `Active ${formatDuration(now - Date.parse(event.raisedAt))}`}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SheetContent>
    </Sheet>
  );
}

function FilterSelect({ id, label, value, onChange, options }: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-xs">{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className="h-8"><SelectValue /></SelectTrigger>
        <SelectContent>{options.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  );
}
