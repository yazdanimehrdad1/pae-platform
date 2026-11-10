import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { knowledgeApi } from "@/api";
import type { GuideSeverity, LimitCondition, LimitGuide, PointGuide } from "@/api/types/knowledge";
import type { ProfilePoint } from "@/api/types/siteProfiles";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/shared/hooks/use-toast";
import { labelsText, localPointName } from "../lib/changes";
import {
  LIMIT_CONDITION_LABELS, SEVERITIES, SEVERITY_LABELS, STATE_KIND_LABELS, type StateRow, linesToList, listToLines,
  rowsToStates, stateRowsFor,
} from "./lib";
import { useKnowledgeEdit } from "./useKnowledge";

// One point's guide, written into the site's draft: what the point means, its normal range, and
// for each state, alarm bit or vendor fault code what it means and what to check. States
// backend-ot labels are listed already; a row counts once it has a message.

interface LimitRow { condition: LimitCondition; value: string; severity: GuideSeverity; message: string; causes: string; checks: string }

const toLimitRow = (limit: LimitGuide): LimitRow => ({
  condition: limit.condition, value: String(limit.value), severity: limit.severity, message: limit.message,
  causes: listToLines(limit.probable_causes), checks: listToLines(limit.checks),
});

function SeveritySelect({ value, onChange, label }: { value: GuideSeverity; onChange: (value: GuideSeverity) => void; label: string }) {
  return (
    <Select value={value} onValueChange={next => onChange(next as GuideSeverity)}>
      <SelectTrigger className="w-full sm:w-32" aria-label={label}><SelectValue /></SelectTrigger>
      <SelectContent>{SEVERITIES.map(severity => <SelectItem key={severity} value={severity}>{SEVERITY_LABELS[severity]}</SelectItem>)}</SelectContent>
    </Select>
  );
}

export function PointGuideDialog({ siteId, point, guide, draftRevision, onClose }: {
  siteId: number;
  point: ProfilePoint;
  guide: PointGuide | undefined;
  draftRevision: number;
  onClose: () => void;
}) {
  const name = localPointName(point);
  const [meaning, setMeaning] = useState(guide?.meaning ?? point.description ?? "");
  const [unitNote, setUnitNote] = useState(guide?.unit_note ?? "");
  const [normalMin, setNormalMin] = useState(guide?.normal_range?.min?.toString() ?? "");
  const [normalMax, setNormalMax] = useState(guide?.normal_range?.max?.toString() ?? "");
  const [related, setRelated] = useState((guide?.related_points ?? []).join(", "));
  const [states, setStates] = useState<StateRow[]>(() => stateRowsFor(point, guide));
  const [limits, setLimits] = useState<LimitRow[]>(() => (guide?.limits ?? []).map(toLimitRow));
  const [newCode, setNewCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const done = { onSaved: () => onClose(), onError: (message: string) => setError(message) };
  const save = useKnowledgeEdit(siteId, () => knowledgeApi.putPointGuide(siteId, point.device_id, name, {
    meaning: meaning.trim(),
    unit_note: unitNote.trim() || null,
    normal_range: normalMin || normalMax ? { min: normalMin ? Number(normalMin) : null, max: normalMax ? Number(normalMax) : null } : null,
    related_points: related.split(",").map(entry => entry.trim()).filter(Boolean),
    states: rowsToStates(states),
    limits: limits.filter(row => row.message.trim() && row.value !== "").map(row => ({
      condition: row.condition, value: Number(row.value), severity: row.severity, message: row.message.trim(),
      probable_causes: linesToList(row.causes), checks: linesToList(row.checks),
    })),
    draft_revision: draftRevision,
  }), { ...done, onSaved: () => { toast({ title: "Guide saved to the draft", description: point.name }); onClose(); } });
  const remove = useKnowledgeEdit(siteId, () => knowledgeApi.deletePointGuide(siteId, point.device_id, name, draftRevision), done);

  const setState = (index: number, change: Partial<StateRow>) =>
    setStates(rows => rows.map((row, at) => (at === index ? { ...row, ...change } : row)));
  const setLimit = (index: number, change: Partial<LimitRow>) =>
    setLimits(rows => rows.map((row, at) => (at === index ? { ...row, ...change } : row)));
  const addFaultCode = () => {
    const code = Number(newCode);
    if (newCode === "" || !Number.isInteger(code)) return;
    setStates(rows => [...rows, { kind: "fault_code", code, label: "", severity: "fault", message: "", meaning: "", causes: "", checks: "", safetyNote: "", fromCatalog: false }]);
    setNewCode("");
  };

  const busy = save.isPending || remove.isPending;
  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-base break-all">{point.name}</DialogTitle>
          <DialogDescription>
            {[point.point_class, point.unit, labelsText(point)].filter(Boolean).join(" · ") || "No labels from backend-ot"}.
            Saved to the draft: the AI uses it after the next publish.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="guide-meaning">Meaning</Label>
            <Textarea id="guide-meaning" value={meaning} onChange={event => setMeaning(event.target.value)} rows={2} placeholder="What this point tells the engineer" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1 sm:col-span-1">
              <Label htmlFor="guide-unit-note">Unit / sign note</Label>
              <Input id="guide-unit-note" value={unitNote} onChange={event => setUnitNote(event.target.value)} placeholder="e.g. positive = export" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="guide-min">Normal min</Label>
              <Input id="guide-min" type="number" value={normalMin} onChange={event => setNormalMin(event.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="guide-max">Normal max</Label>
              <Input id="guide-max" type="number" value={normalMax} onChange={event => setNormalMax(event.target.value)} />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="guide-related">Related points (comma-separated)</Label>
            <Input id="guide-related" value={related} onChange={event => setRelated(event.target.value)} placeholder="e.g. INV1.CabinetTemp, INV1.ActivePower" />
          </div>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold">States, bits and fault codes</h3>
            {states.length === 0 && <p className="text-sm text-muted-foreground">No states from backend-ot. Add vendor fault codes below if the point has them.</p>}
            {states.map((row, index) => (
              <div key={`${row.kind}:${row.code}`} className="rounded-md border p-2 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground w-24 shrink-0">{STATE_KIND_LABELS[row.kind]} {row.code}</span>
                  <Input aria-label={`Label of ${row.kind} ${row.code}`} value={row.label} onChange={event => setState(index, { label: event.target.value })} className="w-full sm:w-44" disabled={row.fromCatalog} />
                  <SeveritySelect label={`Severity of ${row.kind} ${row.code}`} value={row.severity} onChange={severity => setState(index, { severity })} />
                  <Input aria-label={`Message of ${row.kind} ${row.code}`} placeholder="Message (fill to include)" value={row.message} onChange={event => setState(index, { message: event.target.value })} className="flex-1 min-w-[12rem]" />
                  {!row.fromCatalog && (
                    <Button variant="ghost" size="sm" aria-label={`Remove ${row.kind} ${row.code}`} onClick={() => setStates(rows => rows.filter((_, at) => at !== index))}><Trash2 className="w-4 h-4" /></Button>
                  )}
                </div>
                {row.message.trim() && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <Textarea aria-label={`Probable causes of ${row.kind} ${row.code}`} placeholder="Probable causes, one per line" value={row.causes} onChange={event => setState(index, { causes: event.target.value })} rows={2} />
                    <Textarea aria-label={`Checks of ${row.kind} ${row.code}`} placeholder="Checks to make, one per line" value={row.checks} onChange={event => setState(index, { checks: event.target.value })} rows={2} />
                    <Input aria-label={`Meaning of ${row.kind} ${row.code}`} placeholder="Meaning (optional)" value={row.meaning} onChange={event => setState(index, { meaning: event.target.value })} />
                    <Input aria-label={`Safety note of ${row.kind} ${row.code}`} placeholder="Safety note (optional)" value={row.safetyNote} onChange={event => setState(index, { safetyNote: event.target.value })} />
                  </div>
                )}
              </div>
            ))}
            <div className="flex flex-wrap items-center gap-2">
              <Input aria-label="New fault code" type="number" placeholder="Vendor fault code" value={newCode} onChange={event => setNewCode(event.target.value)} className="w-full sm:w-44" />
              <Button variant="outline" size="sm" onClick={addFaultCode} disabled={newCode === ""}><Plus className="w-4 h-4 mr-1" />Add fault code</Button>
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold">Limits</h3>
            {limits.map((row, index) => (
              <div key={index} className="rounded-md border p-2 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Select value={row.condition} onValueChange={condition => setLimit(index, { condition: condition as LimitCondition })}>
                    <SelectTrigger className="w-full sm:w-28" aria-label={`Condition of limit ${index + 1}`}><SelectValue /></SelectTrigger>
                    <SelectContent>{(Object.keys(LIMIT_CONDITION_LABELS) as LimitCondition[]).map(condition => <SelectItem key={condition} value={condition}>{LIMIT_CONDITION_LABELS[condition]}</SelectItem>)}</SelectContent>
                  </Select>
                  <Input aria-label={`Value of limit ${index + 1}`} type="number" value={row.value} onChange={event => setLimit(index, { value: event.target.value })} className="w-full sm:w-28" />
                  <SeveritySelect label={`Severity of limit ${index + 1}`} value={row.severity} onChange={severity => setLimit(index, { severity })} />
                  <Input aria-label={`Message of limit ${index + 1}`} placeholder="Message" value={row.message} onChange={event => setLimit(index, { message: event.target.value })} className="flex-1 min-w-[12rem]" />
                  <Button variant="ghost" size="sm" aria-label={`Remove limit ${index + 1}`} onClick={() => setLimits(rows => rows.filter((_, at) => at !== index))}><Trash2 className="w-4 h-4" /></Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <Textarea aria-label={`Probable causes of limit ${index + 1}`} placeholder="Probable causes, one per line" value={row.causes} onChange={event => setLimit(index, { causes: event.target.value })} rows={2} />
                  <Textarea aria-label={`Checks of limit ${index + 1}`} placeholder="Checks to make, one per line" value={row.checks} onChange={event => setLimit(index, { checks: event.target.value })} rows={2} />
                </div>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setLimits(rows => [...rows, { condition: "above", value: "", severity: "warning", message: "", causes: "", checks: "" }])}>
              <Plus className="w-4 h-4 mr-1" />Add limit
            </Button>
          </section>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter className="gap-2">
          {guide && <Button variant="outline" className="text-destructive" onClick={() => remove.mutate(undefined)} disabled={busy}>Remove guide</Button>}
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => { setError(null); save.mutate(undefined); }} disabled={busy || meaning.trim() === ""}>Save to draft</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
