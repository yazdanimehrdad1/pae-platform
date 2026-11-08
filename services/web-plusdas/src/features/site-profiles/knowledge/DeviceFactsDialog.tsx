import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { knowledgeApi } from "@/api";
import type { DeviceFacts } from "@/api/types/knowledge";
import type { ProfileDevice } from "@/api/types/siteProfiles";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useKnowledgeEdit } from "./useKnowledge";

// What backend-ot doesn't hold about a device: its ratings (e.g. 20 MW, 80 MWh) and notes.

interface RatingRow { name: string; value: string; unit: string }

export function DeviceFactsDialog({ siteId, device, facts, draftRevision, onClose }: {
  siteId: number;
  device: ProfileDevice;
  facts: DeviceFacts | undefined;
  draftRevision: number;
  onClose: () => void;
}) {
  const [ratings, setRatings] = useState<RatingRow[]>(
    () => (facts?.ratings ?? []).map(rating => ({ name: rating.name, value: String(rating.value), unit: rating.unit })),
  );
  const [notes, setNotes] = useState(facts?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const done = { onSaved: () => onClose(), onError: (message: string) => setError(message) };
  const save = useKnowledgeEdit(siteId, () => knowledgeApi.putDeviceFacts(siteId, device.device_id, {
    ratings: ratings
      .filter(row => row.name.trim() && row.value !== "")
      .map(row => ({ name: row.name.trim(), value: Number(row.value), unit: row.unit.trim() })),
    notes: notes.trim() || null,
    draft_revision: draftRevision,
  }), done);
  const remove = useKnowledgeEdit(siteId, () => knowledgeApi.deleteDeviceFacts(siteId, device.device_id, draftRevision), done);
  const setRating = (index: number, change: Partial<RatingRow>) =>
    setRatings(rows => rows.map((row, at) => (at === index ? { ...row, ...change } : row)));
  const busy = save.isPending || remove.isPending;

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{device.name}: ratings and notes</DialogTitle>
          <DialogDescription>{device.type}{device.model ? ` · ${device.model}` : ""}. Saved to the draft.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {ratings.map((row, index) => (
            <div key={index} className="flex flex-wrap items-center gap-2">
              <Input aria-label={`Rating ${index + 1} name`} placeholder="e.g. Energy capacity" value={row.name} onChange={event => setRating(index, { name: event.target.value })} className="flex-1 min-w-[10rem]" />
              <Input aria-label={`Rating ${index + 1} value`} type="number" placeholder="80" value={row.value} onChange={event => setRating(index, { value: event.target.value })} className="w-full sm:w-28" />
              <Input aria-label={`Rating ${index + 1} unit`} placeholder="MWh" value={row.unit} onChange={event => setRating(index, { unit: event.target.value })} className="w-full sm:w-24" />
              <Button variant="ghost" size="sm" aria-label={`Remove rating ${index + 1}`} onClick={() => setRatings(rows => rows.filter((_, at) => at !== index))}><Trash2 className="w-4 h-4" /></Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => setRatings(rows => [...rows, { name: "", value: "", unit: "" }])}><Plus className="w-4 h-4 mr-1" />Add rating</Button>
          <div className="space-y-1">
            <Label htmlFor="device-notes">Notes</Label>
            <Textarea id="device-notes" value={notes} onChange={event => setNotes(event.target.value)} rows={4} placeholder="e.g. Replaced in 2025; 4 strings" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter className="gap-2">
          {facts && <Button variant="outline" className="text-destructive" onClick={() => remove.mutate(undefined)} disabled={busy}>Remove</Button>}
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => { setError(null); save.mutate(undefined); }} disabled={busy}>Save to draft</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
