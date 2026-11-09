import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus2, History, Pencil, Send, Trash2, Undo2 } from "lucide-react";
import { knowledgeApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { DeviceFacts, KnowledgeChange, KnowledgeDocument, KnowledgeState, PointGuide } from "@/api/types/knowledge";
import type { ProfilePoint, ProfileVersion } from "@/api/types/siteProfiles";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EDIT_ON_LARGER_SCREEN, HideOnPhone } from "@/shared/components/HideOnPhone";
import { toast } from "@/shared/hooks/use-toast";
import { formatDateTime, localPointName, statusOf } from "../lib/changes";
import { DeviceFactsDialog } from "./DeviceFactsDialog";
import { DocumentDialog } from "./DocumentDialog";
import { PointGuideDialog } from "./PointGuideDialog";
import { SitePrompts } from "./SitePrompts";
import {
  DOCUMENT_KIND_LABELS, ITEM_STATUS_LABELS, type ItemStatus, documentKey, factsKey, guideKey, isDraftConflict, itemStatus,
  knowledgeQueryKey,
} from "./lib";
import { useKnowledge, useKnowledgeEdit } from "./useKnowledge";

// The site's engineer knowledge: site prompts (general information, step by step), what each point
// means and what to do about each state or fault code, documents, and device ratings. Edits go to a draft; "Review & publish" makes the whole
// draft the version the AI uses (the site at once).

const STATUS_STYLES: Record<ItemStatus, string> = {
  published: "bg-success/10 text-success border-success",
  added: "bg-warning/10 text-warning border-warning",
  changed: "bg-warning/10 text-warning border-warning",
  removed: "bg-destructive/10 text-destructive border-destructive",
  none: "text-muted-foreground",
};

/** Status, alarm and fault-code points come first: they need a guide most. */
function needsGuideFirst(point: ProfilePoint): boolean {
  return point.point_class === "ALARM" || Object.keys(point.enum_labels ?? {}).length > 0 || Object.keys(point.bit_labels ?? {}).length > 0;
}

function StatusBadge({ status }: { status: ItemStatus }) {
  return <Badge variant="outline" className={STATUS_STYLES[status]}>{ITEM_STATUS_LABELS[status]}</Badge>;
}

export function KnowledgePanel({ siteId, profile }: { siteId: number; profile: ProfileVersion | undefined }) {
  const { data: state, isLoading, isError, error } = useKnowledge(siteId);
  const [reviewing, setReviewing] = useState(false);

  if (!profile) return <p className="text-muted-foreground">Onboard the site first: knowledge is written for its approved devices and points.</p>;
  if (isLoading) return <p className="text-muted-foreground">Loading the knowledge...</p>;
  if (isError || !state) return <p className="text-destructive">Could not load the knowledge: {getErrorMessage(error)}</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3">
        <div className="text-sm">
          <p>
            {state.published_version
              ? <>The AI uses <strong>version {state.published_version}</strong>, published {formatDateTime(state.published_at)} by {state.published_by}.</>
              : "Nothing published yet: the AI has no engineer knowledge for this site."}
          </p>
          <p className="text-muted-foreground">
            {state.changes.length > 0
              ? `${state.changes.length} unpublished change(s) in the draft (last saved ${formatDateTime(state.draft_updated_at)} by ${state.draft_updated_by}).`
              : "No unpublished changes."}
          </p>
        </div>
        <HideOnPhone note={EDIT_ON_LARGER_SCREEN}>
          <Button onClick={() => setReviewing(true)} disabled={state.changes.length === 0}>
            <Send className="w-4 h-4 mr-2" />Review & publish ({state.changes.length})
          </Button>
        </HideOnPhone>
      </div>

      <Tabs defaultValue="site-prompts">
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="site-prompts">Site Prompts ({state.content.site_prompts?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="points">Point guides</TabsTrigger>
          <TabsTrigger value="documents">Documents ({state.content.documents?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="devices">Device ratings</TabsTrigger>
          <TabsTrigger value="versions">Versions</TabsTrigger>
        </TabsList>
        <TabsContent value="site-prompts" className="pt-2"><SitePrompts siteId={siteId} profile={profile} state={state} /></TabsContent>
        <TabsContent value="points" className="pt-2"><PointGuides siteId={siteId} profile={profile} state={state} /></TabsContent>
        <TabsContent value="documents" className="pt-2"><Documents siteId={siteId} profile={profile} state={state} /></TabsContent>
        <TabsContent value="devices" className="pt-2"><Devices siteId={siteId} profile={profile} state={state} /></TabsContent>
        <TabsContent value="versions" className="pt-2"><Versions siteId={siteId} state={state} /></TabsContent>
      </Tabs>

      {reviewing && <PublishDialog siteId={siteId} state={state} onClose={() => setReviewing(false)} />}
    </div>
  );
}

const ALL_DEVICES = "all";

function PointGuides({ siteId, profile, state }: { siteId: number; profile: ProfileVersion; state: KnowledgeState }) {
  const [filter, setFilter] = useState("");
  const [deviceFilter, setDeviceFilter] = useState(ALL_DEVICES);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [editing, setEditing] = useState<ProfilePoint | null>(null);
  const guides = useMemo(() => {
    const byKey = new Map<string, PointGuide>();
    for (const guide of state.content.point_guides ?? []) byKey.set(guideKey(guide.device_id, guide.point_name), guide);
    return byKey;
  }, [state]);

  const deviceNames = new Map(profile.catalog.devices.map(device => [device.device_id, device.name]));
  const devicesByName = [...profile.catalog.devices].sort((left, right) => left.name.localeCompare(right.name));

  const points = profile.catalog.points
    .filter(point => deviceFilter === ALL_DEVICES || String(point.device_id) === deviceFilter)
    .filter(point => !filter.trim() || point.name.toLowerCase().includes(filter.trim().toLowerCase()))
    .filter(point => !onlyMissing || (needsGuideFirst(point) && !guides.has(guideKey(point.device_id, localPointName(point)))))
    .sort((left, right) => Number(needsGuideFirst(right)) - Number(needsGuideFirst(left)) || left.name.localeCompare(right.name));
  const discrete = profile.catalog.points.filter(needsGuideFirst);
  const covered = discrete.filter(point => guides.has(guideKey(point.device_id, localPointName(point)))).length;

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Status, alarm and fault-code points with a guide: <strong className="text-foreground">{covered} of {discrete.length}</strong>. They are listed first.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Input placeholder="Filter points" aria-label="Filter points" value={filter} onChange={event => setFilter(event.target.value)} className="w-full sm:w-72" />
        <select
          aria-label="Filter by device"
          value={deviceFilter}
          onChange={event => setDeviceFilter(event.target.value)}
          className="flex h-9 w-full sm:w-56 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <option value={ALL_DEVICES}>All devices</option>
          {devicesByName.map(device => <option key={device.device_id} value={String(device.device_id)}>{device.name}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={onlyMissing} onCheckedChange={setOnlyMissing} aria-label="Only points that need a guide" />
          Only points that need a guide
        </label>
      </div>
      <div className="overflow-x-auto rounded-md border max-h-[36rem] overflow-y-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Device</TableHead>
              <TableHead>Point</TableHead>
              <TableHead>Class</TableHead>
              <TableHead>Guide</TableHead>
              <TableHead>Meaning</TableHead>
              <TableHead className="text-right">Edit</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {points.map(point => {
              const key = guideKey(point.device_id, localPointName(point));
              const guide = guides.get(key);
              return (
                <TableRow key={point.name}>
                  <TableCell className="whitespace-nowrap">{deviceNames.get(point.device_id) ?? point.device_name}</TableCell>
                  <TableCell className="font-mono text-xs whitespace-nowrap">{localPointName(point)}</TableCell>
                  <TableCell>{point.point_class ?? ""}</TableCell>
                  <TableCell><StatusBadge status={itemStatus(key, guide !== undefined, state.changes)} /></TableCell>
                  <TableCell className="max-w-md truncate">{guide?.meaning ?? ""}</TableCell>
                  <TableCell className="text-right">
                    <HideOnPhone>
                      <Button variant="ghost" size="sm" aria-label={`Edit the guide of ${point.name}`} onClick={() => setEditing(point)}><Pencil className="w-4 h-4" /></Button>
                    </HideOnPhone>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      {editing && (
        <PointGuideDialog
          siteId={siteId}
          point={editing}
          guide={guides.get(guideKey(editing.device_id, localPointName(editing)))}
          draftRevision={state.draft_revision}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function Documents({ siteId, profile, state }: { siteId: number; profile: ProfileVersion; state: KnowledgeState }) {
  const [editing, setEditing] = useState<KnowledgeDocument | "new" | null>(null);
  const devices = new Map(profile.catalog.devices.map(device => [device.device_id, device.name]));
  const documents = state.content.documents ?? [];
  return (
    <div className="space-y-3">
      <HideOnPhone note={EDIT_ON_LARGER_SCREEN}>
        <Button variant="outline" onClick={() => setEditing("new")}><FilePlus2 className="w-4 h-4 mr-2" />Add document</Button>
      </HideOnPhone>
      {documents.length === 0 && <p className="text-muted-foreground">No documents yet: manuals, IM scripts, procedures and experience notes.</p>}
      {documents.length > 0 && (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Device</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Edit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map(document => (
                <TableRow key={document.document_id}>
                  <TableCell className="font-medium">{document.title}</TableCell>
                  <TableCell>{DOCUMENT_KIND_LABELS[document.kind]}</TableCell>
                  <TableCell>{document.device_id != null ? devices.get(document.device_id) ?? `#${document.device_id}` : "Site"}</TableCell>
                  <TableCell><StatusBadge status={itemStatus(documentKey(document.document_id ?? ""), true, state.changes)} /></TableCell>
                  <TableCell className="text-right">
                    <HideOnPhone>
                      <Button variant="ghost" size="sm" aria-label={`Edit ${document.title}`} onClick={() => setEditing(document)}><Pencil className="w-4 h-4" /></Button>
                    </HideOnPhone>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {editing && (
        <DocumentDialog
          siteId={siteId}
          document={editing === "new" ? undefined : editing}
          devices={profile.catalog.devices}
          draftRevision={state.draft_revision}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function Devices({ siteId, profile, state }: { siteId: number; profile: ProfileVersion; state: KnowledgeState }) {
  const [editing, setEditing] = useState<number | null>(null);
  const facts = new Map<number, DeviceFacts>((state.content.device_facts ?? []).map(entry => [entry.device_id, entry]));
  const device = profile.catalog.devices.find(entry => entry.device_id === editing);
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Device</TableHead>
              <TableHead>Ratings</TableHead>
              <TableHead>Notes</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Edit</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {profile.catalog.devices.map(entry => {
              const known = facts.get(entry.device_id);
              return (
                <TableRow key={entry.device_id}>
                  <TableCell className="font-medium whitespace-nowrap">{entry.name} <span className="text-muted-foreground text-xs">{entry.type}</span></TableCell>
                  <TableCell className="text-sm">{(known?.ratings ?? []).map(rating => `${rating.name} ${rating.value} ${rating.unit}`).join(" · ")}</TableCell>
                  <TableCell className="max-w-xs truncate text-sm">{known?.notes ?? ""}</TableCell>
                  <TableCell><StatusBadge status={itemStatus(factsKey(entry.device_id), known !== undefined, state.changes)} /></TableCell>
                  <TableCell className="text-right">
                    <HideOnPhone>
                      <Button variant="ghost" size="sm" aria-label={`Edit the ratings of ${entry.name}`} onClick={() => setEditing(entry.device_id)}><Pencil className="w-4 h-4" /></Button>
                    </HideOnPhone>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      {device && (
        <DeviceFactsDialog siteId={siteId} device={device} facts={facts.get(device.device_id)} draftRevision={state.draft_revision} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

function Versions({ siteId, state }: { siteId: number; state: KnowledgeState }) {
  const queryClient = useQueryClient();
  const { data: versions = [], isLoading } = useQuery({
    queryKey: ["site-profiles", siteId, "knowledge-versions", state.published_version],
    queryFn: () => knowledgeApi.versions(siteId),
  });
  const restore = useMutation({
    mutationFn: (version: number) => knowledgeApi.restore(siteId, version),
    onSuccess: (version) => {
      toast({ title: `Restored as version ${version.version}`, description: `The AI uses version ${version.restored_from}'s content again.` });
      queryClient.invalidateQueries({ queryKey: ["site-profiles", siteId] });
    },
    onError: (restoreError) => toast({ title: "Could not restore", description: getErrorMessage(restoreError), variant: "destructive" }),
  });
  const [selected, setSelected] = useState<number[]>([]);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const deleteVersions = useMutation({
    mutationFn: (numbers: number[]) => knowledgeApi.deleteVersions(siteId, numbers),
    onSuccess: (_remaining, numbers) => {
      toast({ title: `Deleted ${numbers.length} version(s)`, description: "What the AI uses didn't change." });
      setSelected([]);
      queryClient.invalidateQueries({ queryKey: ["site-profiles", siteId] });
    },
    onError: (deleteError) => toast({ title: "Could not delete", description: getErrorMessage(deleteError), variant: "destructive" }),
  });
  if (isLoading) return <p className="text-muted-foreground">Loading versions...</p>;
  if (versions.length === 0) return <p className="text-muted-foreground">Nothing published yet.</p>;
  const hasDraft = state.draft_revision > 0;
  // The version the AI uses can't be deleted; only older ones are selectable.
  const deletable = versions.map(version => version.version).filter(number => number !== state.published_version);
  const chosen = selected.filter(number => deletable.includes(number)).sort((left, right) => left - right);
  const allChosen = deletable.length > 0 && chosen.length === deletable.length;
  const toggle = (number: number, checked: boolean) =>
    setSelected(current => (checked ? [...current, number] : current.filter(entry => entry !== number)));
  return (
    <div className="space-y-2">
      {hasDraft && <p className="text-sm text-muted-foreground">Publish or discard the draft before restoring a version.</p>}
      <HideOnPhone>
        <Button variant="outline" className="text-destructive" disabled={chosen.length === 0 || deleteVersions.isPending} onClick={() => setConfirmingDelete(true)}>
          <Trash2 className="w-4 h-4 mr-2" />Delete selected ({chosen.length})
        </Button>
      </HideOnPhone>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <Checkbox
                  aria-label="Select all older versions"
                  checked={allChosen ? true : chosen.length > 0 ? "indeterminate" : false}
                  disabled={deletable.length === 0}
                  onCheckedChange={checked => setSelected(checked === true ? deletable : [])}
                />
              </TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Published</TableHead>
              <TableHead>By</TableHead>
              <TableHead>Changes</TableHead>
              <TableHead>Scripts · guides · documents · devices</TableHead>
              <TableHead className="text-right">Restore</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {versions.map(version => (
              <TableRow key={version.version}>
                <TableCell>
                  {version.version !== state.published_version && (
                    <Checkbox
                      aria-label={`Select version ${version.version}`}
                      checked={chosen.includes(version.version)}
                      onCheckedChange={checked => toggle(version.version, checked === true)}
                    />
                  )}
                </TableCell>
                <TableCell className="font-medium">
                  v{version.version}{version.restored_from ? <span className="text-muted-foreground"> (from v{version.restored_from})</span> : null}
                  {version.version === state.published_version && <Badge variant="outline" className="ml-2">AI uses this</Badge>}
                </TableCell>
                <TableCell className="whitespace-nowrap">{formatDateTime(version.published_at)}</TableCell>
                <TableCell>{version.published_by}</TableCell>
                <TableCell>{version.change_ids.length}</TableCell>
                <TableCell>{version.site_prompts} · {version.point_guides} · {version.documents} · {version.device_facts}</TableCell>
                <TableCell className="text-right">
                  {version.version !== state.published_version && (
                    <HideOnPhone>
                      <Button variant="ghost" size="sm" aria-label={`Restore version ${version.version}`} disabled={hasDraft || restore.isPending} onClick={() => restore.mutate(version.version)}>
                        <History className="w-4 h-4" />
                      </Button>
                    </HideOnPhone>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AlertDialog open={confirmingDelete} onOpenChange={setConfirmingDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {chosen.length} version(s)?</AlertDialogTitle>
            <AlertDialogDescription>
              {chosen.map(number => `v${number}`).join(", ")} will be gone for good and can't be restored later.
              The AI keeps using version {state.published_version}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => deleteVersions.mutate(chosen)}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function PublishDialog({ siteId, state, onClose }: { siteId: number; state: KnowledgeState; onClose: () => void }) {
  const queryClient = useQueryClient();
  const revert = useKnowledgeEdit(siteId, (change: KnowledgeChange) => knowledgeApi.revert(siteId, [change.item_key], state.draft_revision));
  const discard = useKnowledgeEdit(siteId, () => knowledgeApi.discardDraft(siteId), { onSaved: () => onClose() });
  const publish = useMutation({
    mutationFn: () => knowledgeApi.publish(siteId, state.draft_revision),
    onSuccess: (version) => {
      toast({ title: `Published version ${version.version}`, description: `${version.change_ids.length} change(s). The AI uses them now.` });
      queryClient.invalidateQueries({ queryKey: ["site-profiles", siteId] });
      onClose();
    },
    onError: (publishError) => {
      if (isDraftConflict(publishError) || statusOf(publishError) === 422) queryClient.invalidateQueries({ queryKey: knowledgeQueryKey(siteId) });
      toast({ title: "Could not publish", description: getErrorMessage(publishError), variant: "destructive" });
    },
  });
  const busy = revert.isPending || discard.isPending || publish.isPending;

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Publish the draft</DialogTitle>
          <DialogDescription>
            Everything below goes live for the AI at once, as version {(state.published_version ?? 0) + 1}. Put back what shouldn't go yet.
          </DialogDescription>
        </DialogHeader>
        {state.changes.length === 0 && <p className="text-muted-foreground">Nothing left to publish.</p>}
        <ul className="divide-y rounded-md border">
          {state.changes.map(change => (
            <li key={change.item_key} className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="text-sm break-words">{change.summary}</span>
              <Button variant="ghost" size="sm" aria-label={`Put back ${change.summary}`} onClick={() => revert.mutate(change)} disabled={busy}>
                <Undo2 className="w-4 h-4 mr-1" />Put back
              </Button>
            </li>
          ))}
        </ul>
        <DialogFooter className="gap-2">
          <Button variant="outline" className="text-destructive" onClick={() => discard.mutate(undefined)} disabled={busy}>Discard the whole draft</Button>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => publish.mutate()} disabled={busy || state.changes.length === 0}><Send className="w-4 h-4 mr-2" />Publish</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
