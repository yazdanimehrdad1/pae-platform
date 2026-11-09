import { useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { knowledgeApi } from "@/api";
import type { KnowledgeState, SiteScript } from "@/api/types/knowledge";
import type { ProfileVersion } from "@/api/types/siteProfiles";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EDIT_ON_LARGER_SCREEN, HideOnPhone } from "@/shared/components/HideOnPhone";
import { ITEM_STATUS_LABELS, itemStatus, scriptKey } from "./lib";
import { LinkBadges, PromptLinksEditor } from "./PromptLinks";
import { linkOptions, linkValues, valuesToLinks } from "./linkValues";
import { useKnowledgeEdit } from "./useKnowledge";

// Site prompts: the admin's general information about the site for the AI, entered as several
// named texts (overview, how it runs, scripts...) instead of one long prompt. Each is saved to the
// draft; the AI reads them all, in this order, at the top of its site context after a publish.

const MAX_TEXT = 20_000;

type Options = ReturnType<typeof linkOptions>;

export function SiteScripts({ siteId, profile, state }: { siteId: number; profile: ProfileVersion; state: KnowledgeState }) {
  const scripts = state.content.site_scripts ?? [];
  const options = useMemo(() => linkOptions(profile, state), [profile, state]);
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        General information about the site, one prompt at a time: a name and text per prompt. The AI reads every prompt, in this order, before anything else about the site.
      </p>
      {scripts.length === 0 && <p className="text-muted-foreground">No site prompts yet. Start with an overview of the site.</p>}
      <ol className="space-y-3">
        {scripts.map((script, index) => (
          <li key={script.script_id} className="rounded-md border p-3">
            {editingId === script.script_id ? (
              <ScriptForm
                siteId={siteId}
                state={state}
                options={options}
                script={script}
                step={index + 1}
                onDone={() => setEditingId(null)}
              />
            ) : (
              <ScriptView siteId={siteId} state={state} options={options} script={script} step={index + 1} onEdit={() => setEditingId(script.script_id)} />
            )}
          </li>
        ))}
      </ol>
      <HideOnPhone note={EDIT_ON_LARGER_SCREEN}>
        <div className="rounded-md border border-dashed p-3">
          <ScriptForm siteId={siteId} state={state} options={options} step={scripts.length + 1} />
        </div>
      </HideOnPhone>
    </div>
  );
}

function ScriptView({ siteId, state, options, script, step, onEdit }: {
  siteId: number;
  state: KnowledgeState;
  options: Options;
  script: SiteScript;
  step: number;
  onEdit: () => void;
}) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const remove = useKnowledgeEdit(siteId, () => knowledgeApi.deleteSiteScript(siteId, script.script_id, state.draft_revision));
  const status = itemStatus(scriptKey(script.script_id), true, state.changes);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-medium"><span className="text-muted-foreground mr-2">Prompt {step}:</span>{script.name}</h3>
          <Badge variant="outline" className="font-normal">{ITEM_STATUS_LABELS[status]}</Badge>
        </div>
        <HideOnPhone>
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" aria-label={`Edit ${script.name}`} onClick={onEdit}><Pencil className="w-4 h-4" /></Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive"
              aria-label={`Delete ${script.name}`}
              disabled={remove.isPending}
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </HideOnPhone>
      </div>
      <p className="whitespace-pre-wrap text-sm">{script.text}</p>
      <LinkBadges options={options} values={linkValues(script.links)} />
      <AlertDialog open={confirmingDelete} onOpenChange={setConfirmingDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{script.name}"?</AlertDialogTitle>
            <AlertDialogDescription>
              {status === "added"
                ? "It was never published, so its text is lost."
                : "It is removed in the draft; the AI stops reading it after the next publish. Until then you can put it back from Review & publish."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => remove.mutate(undefined)}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/** Adds the next prompt, or (with `script`) changes that one. */
function ScriptForm({ siteId, state, options, script, step, onDone }: {
  siteId: number;
  state: KnowledgeState;
  options: Options;
  script?: SiteScript;
  step: number;
  onDone?: () => void;
}) {
  const [name, setName] = useState(script?.name ?? "");
  const [text, setText] = useState(script?.text ?? "");
  const [links, setLinks] = useState(() => linkValues(script?.links));
  const [error, setError] = useState<string | null>(null);
  const request = () => ({ name: name.trim(), text, links: valuesToLinks(links), draft_revision: state.draft_revision });
  const save = useKnowledgeEdit(
    siteId,
    () => (script ? knowledgeApi.updateSiteScript(siteId, script.script_id, request()) : knowledgeApi.createSiteScript(siteId, request())),
    {
      onSaved: () => {
        if (!script) { setName(""); setText(""); setLinks(linkValues(undefined)); }
        onDone?.();
      },
      onError: (message: string) => setError(message),
    },
  );
  const prefix = script ? `script-${script.script_id}` : "script-new";
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{script ? `Edit prompt ${step}` : `Add prompt ${step}`}</p>
      <div className="space-y-1">
        <Label htmlFor={`${prefix}-name`}>Name</Label>
        <Input id={`${prefix}-name`} value={name} onChange={event => setName(event.target.value)} maxLength={200} placeholder="e.g. Overview" />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`${prefix}-text`}>Information</Label>
        <Textarea
          id={`${prefix}-text`}
          value={text}
          onChange={event => setText(event.target.value)}
          rows={6}
          placeholder="What the AI should know. Never paste passwords or IP addresses."
        />
        <p className="text-xs text-muted-foreground text-right">{text.length.toLocaleString()} / {MAX_TEXT.toLocaleString()}</p>
      </div>
      <PromptLinksEditor options={options} values={links} onChange={setLinks} />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex justify-end gap-2">
        {onDone && <Button variant="ghost" onClick={onDone}>Cancel</Button>}
        <Button
          onClick={() => { setError(null); save.mutate(undefined); }}
          disabled={save.isPending || !name.trim() || !text.trim() || text.length > MAX_TEXT}
        >
          {script ? "Save to draft" : <><Plus className="w-4 h-4 mr-1" />Submit to draft</>}
        </Button>
      </div>
    </div>
  );
}
