import { useState } from "react";
import { knowledgeApi } from "@/api";
import type { KnowledgeDocument, KnowledgeKind } from "@/api/types/knowledge";
import type { ProfileDevice } from "@/api/types/siteProfiles";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { DOCUMENT_KINDS, DOCUMENT_KIND_LABELS } from "./lib";
import { useKnowledgeEdit } from "./useKnowledge";

// A manual, IM script, procedure or experience note: pasted text, optionally about one device.
// IM scripts, manuals and procedures go into the AI's site context; notes are searched by keyword.

const NO_DEVICE = "none";
const MAX_BODY = 50_000;

export function DocumentDialog({ siteId, document, devices, draftRevision, onClose }: {
  siteId: number;
  document?: KnowledgeDocument;
  devices: ProfileDevice[];
  draftRevision: number;
  onClose: () => void;
}) {
  const [kind, setKind] = useState<KnowledgeKind>(document?.kind ?? "procedure");
  const [title, setTitle] = useState(document?.title ?? "");
  const [body, setBody] = useState(document?.body ?? "");
  const [deviceId, setDeviceId] = useState(document?.device_id != null ? String(document.device_id) : NO_DEVICE);
  const [error, setError] = useState<string | null>(null);

  const request = () => ({
    kind,
    title: title.trim(),
    body,
    device_id: deviceId === NO_DEVICE ? null : Number(deviceId),
    point_names: document?.point_names ?? [],
    draft_revision: draftRevision,
  });
  const done = { onSaved: () => onClose(), onError: (message: string) => setError(message) };
  const save = useKnowledgeEdit(
    siteId,
    () => (document ? knowledgeApi.updateDocument(siteId, document.document_id, request()) : knowledgeApi.createDocument(siteId, request())),
    done,
  );
  const remove = useKnowledgeEdit(siteId, () => knowledgeApi.deleteDocument(siteId, document!.document_id, draftRevision), done);
  const busy = save.isPending || remove.isPending;

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{document ? "Edit document" : "Add document"}</DialogTitle>
          <DialogDescription>Paste the text. Saved to the draft: the AI uses it after the next publish. Never paste passwords or IP addresses.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="document-kind">Kind</Label>
              <Select value={kind} onValueChange={next => setKind(next as KnowledgeKind)}>
                <SelectTrigger id="document-kind" aria-label="Kind"><SelectValue /></SelectTrigger>
                <SelectContent>{DOCUMENT_KINDS.map(entry => <SelectItem key={entry} value={entry}>{DOCUMENT_KIND_LABELS[entry]}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="document-device">Device</Label>
              <Select value={deviceId} onValueChange={setDeviceId}>
                <SelectTrigger id="document-device" aria-label="Device"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_DEVICE}>The whole site</SelectItem>
                  {devices.map(device => <SelectItem key={device.device_id} value={String(device.device_id)}>{device.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="document-title">Title</Label>
            <Input id="document-title" value={title} onChange={event => setTitle(event.target.value)} maxLength={200} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="document-body">Text</Label>
            <Textarea id="document-body" value={body} onChange={event => setBody(event.target.value)} rows={14} className="font-mono text-xs" />
            <p className="text-xs text-muted-foreground text-right">{body.length.toLocaleString()} / {MAX_BODY.toLocaleString()}</p>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter className="gap-2">
          {document && <Button variant="outline" className="text-destructive" onClick={() => remove.mutate(undefined)} disabled={busy}>Remove</Button>}
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => { setError(null); save.mutate(undefined); }} disabled={busy || !title.trim() || !body.trim() || body.length > MAX_BODY}>Save to draft</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
