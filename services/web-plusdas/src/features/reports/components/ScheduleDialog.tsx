import { useState } from "react";
import type { ReportCadence, ReportScheduleCreateRequest, ReportScheduleRecord, ReportTemplateRecord, ReportWindow } from "@/api/types/reports";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { CADENCE_KIND_LABELS, defaultCadence, WEEKDAY_NAMES, type CadenceKind } from "../lib/cadence";
import { windowLabel } from "../lib/format";
import { WindowEditor } from "./builder/WindowEditor";

const DAYS_OF_MONTH = Array.from({ length: 28 }, (_, index) => index + 1);

export type ScheduleDraft = ReportScheduleCreateRequest;

function draftFrom(schedule: ReportScheduleRecord | null, templateId: number | null): ScheduleDraft {
  if (schedule) {
    return {
      template_id: schedule.template_id, cadence: schedule.cadence, window_override: schedule.window_override ?? null,
      enabled: schedule.enabled, keep_last: schedule.keep_last ?? null, keep_days: schedule.keep_days ?? null,
    };
  }
  return { template_id: templateId ?? 0, cadence: defaultCadence("daily"), window_override: null, enabled: true, keep_last: 30, keep_days: null };
}

/** A positive whole number from an input, or null when it is left empty. */
function countOrNull(value: string): number | null {
  const count = Math.floor(Number(value));
  return value.trim() === "" || !Number.isFinite(count) || count < 1 ? null : count;
}

/** Create or change a schedule: which template, how often (site time), which period, how many reports to keep. */
export function ScheduleDialog({ open, onOpenChange, schedule, templateId, templates, timeZone, isSaving, onSave }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  schedule: ReportScheduleRecord | null;
  templateId: number | null;
  templates: ReportTemplateRecord[];
  timeZone: string;
  isSaving: boolean;
  onSave: (draft: ScheduleDraft) => void;
}) {
  const [draft, setDraft] = useState<ScheduleDraft>(() => draftFrom(schedule, templateId));
  const template = templates.find(candidate => candidate.id === draft.template_id);
  const cadence = draft.cadence;
  const setCadence = (next: ReportCadence) => setDraft({ ...draft, cadence: next });
  const weekdaysMissing = cadence.kind === "weekly" && cadence.weekdays.length === 0;
  const canSave = Boolean(template) && !weekdaysMissing && !isSaving;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{schedule ? "Change schedule" : "Schedule a report"}</DialogTitle>
          <DialogDescription>Times are on the site's clock ({timeZone}). Each time, the template's current version is generated.</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="space-y-1">
            <Label htmlFor="schedule-template">Template</Label>
            <Select value={draft.template_id ? String(draft.template_id) : undefined} onValueChange={value => setDraft({ ...draft, template_id: Number(value) })} disabled={schedule !== null}>
              <SelectTrigger id="schedule-template"><SelectValue placeholder="Choose a template" /></SelectTrigger>
              <SelectContent>{templates.map(candidate => <SelectItem key={candidate.id} value={String(candidate.id)}>{candidate.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">How often</legend>
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1">
                <Label htmlFor="schedule-kind">Repeat</Label>
                <Select value={cadence.kind} onValueChange={kind => setCadence(defaultCadence(kind as CadenceKind))}>
                  <SelectTrigger id="schedule-kind" className="w-40"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(Object.keys(CADENCE_KIND_LABELS) as CadenceKind[]).map(kind => <SelectItem key={kind} value={kind}>{CADENCE_KIND_LABELS[kind]}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {cadence.kind === "hourly" ? (
                <div className="space-y-1">
                  <Label htmlFor="schedule-minute">At minute</Label>
                  <Input
                    id="schedule-minute" type="number" min={0} max={59} className="w-24" value={cadence.minute ?? 0}
                    onChange={event => setCadence({ ...cadence, minute: Math.min(59, Math.max(0, Math.floor(Number(event.target.value)) || 0)) })}
                  />
                </div>
              ) : (
                <div className="space-y-1">
                  <Label htmlFor="schedule-time">At</Label>
                  <Input id="schedule-time" type="time" className="w-32" value={cadence.time} onChange={event => event.target.value && setCadence({ ...cadence, time: event.target.value })} />
                </div>
              )}
              {cadence.kind === "monthly" && (
                <div className="space-y-1">
                  <Label htmlFor="schedule-day">On day</Label>
                  <Select value={String(cadence.day_of_month)} onValueChange={day => setCadence({ ...cadence, day_of_month: Number(day) })}>
                    <SelectTrigger id="schedule-day" className="w-24"><SelectValue /></SelectTrigger>
                    <SelectContent>{DAYS_OF_MONTH.map(day => <SelectItem key={day} value={String(day)}>{day}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              )}
            </div>
            {cadence.kind === "weekly" && (
              <div className="flex flex-wrap gap-4" role="group" aria-label="Weekdays">
                {WEEKDAY_NAMES.map((name, day) => (
                  <label key={name} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={cadence.weekdays.includes(day)}
                      onCheckedChange={checked => setCadence({
                        ...cadence,
                        weekdays: checked === true ? [...cadence.weekdays, day].sort((first, second) => first - second) : cadence.weekdays.filter(candidate => candidate !== day),
                      })}
                    />
                    {name}
                  </label>
                ))}
              </div>
            )}
            {weekdaysMissing && <p role="alert" className="text-sm text-destructive">Choose at least one weekday</p>}
            {cadence.kind === "monthly" && <p className="text-xs text-muted-foreground">Days 1 to 28, so it runs every month.</p>}
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">Period each report covers</legend>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={draft.window_override === null || draft.window_override === undefined}
                onCheckedChange={checked => setDraft({ ...draft, window_override: checked === true ? null : (template?.definition.window ?? { kind: "calendar", period: "day", offset: -1 }) })}
              />
              The template's period{template ? ` (${windowLabel(template.definition.window)})` : ""}
            </label>
            {draft.window_override && (
              <WindowEditor
                window={draft.window_override as ReportWindow} timeZone={timeZone} problems={[]}
                onChange={window => setDraft({ ...draft, window_override: window })}
              />
            )}
            <p className="text-xs text-muted-foreground">Worked out at each scheduled time: a report due at 06:00 for "Yesterday" covers the day before.</p>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">Reports to keep</legend>
            <div className="flex flex-wrap gap-3">
              <div className="space-y-1">
                <Label htmlFor="schedule-keep-last">The last</Label>
                <Input id="schedule-keep-last" type="number" min={1} placeholder="all" className="w-28" value={draft.keep_last ?? ""} onChange={event => setDraft({ ...draft, keep_last: countOrNull(event.target.value) })} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="schedule-keep-days">Days at most</Label>
                <Input id="schedule-keep-days" type="number" min={1} placeholder="forever" className="w-28" value={draft.keep_days ?? ""} onChange={event => setDraft({ ...draft, keep_days: countOrNull(event.target.value) })} />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">Only this schedule's reports are deleted; reports generated by hand always stay. Leave both empty to keep every report.</p>
          </fieldset>

          <label className="flex items-center gap-2 text-sm">
            <Switch checked={draft.enabled ?? true} onCheckedChange={enabled => setDraft({ ...draft, enabled })} aria-label="Enabled" />
            Enabled
          </label>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!canSave} onClick={() => onSave(draft)}>{isSaving ? "Saving..." : schedule ? "Save schedule" : "Create schedule"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
