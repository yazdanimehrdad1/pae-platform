import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck, RefreshCw } from "lucide-react";
import { siteProfilesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ChangeKind, PendingChanges } from "@/api/types/siteProfiles";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EDIT_ON_LARGER_SCREEN, HideOnPhone } from "@/shared/components/HideOnPhone";
import { toast } from "@/shared/hooks/use-toast";
import {
  CHANGE_KIND_LABELS, CHANGE_TARGET_LABELS, approvalProblem, formatDateTime, groupByTarget, statusOf,
} from "../lib/changes";

// The differences between backend-ot (as last read) and what the AI may use. Reading backend-ot
// again changes nothing for the AI; approving the chosen changes makes the next profile version.

const KIND_STYLES: Record<ChangeKind, string> = {
  added: "bg-success/10 text-success border-success",
  removed: "bg-destructive/10 text-destructive border-destructive",
  changed: "bg-warning/10 text-warning border-warning",
};

const changesQueryKey = (siteId: number) => ["site-profiles", siteId, "changes"] as const;

export function PendingChangesPanel({ siteId, onboarded, timeZone }: { siteId: number; onboarded: boolean; timeZone: string }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const { data: pending, isLoading, isError, error } = useQuery({
    queryKey: changesQueryKey(siteId),
    queryFn: () => siteProfilesApi.changes(siteId),
    retry: false,
  });
  // A new read of backend-ot is a new list to review: start the selection over.
  useEffect(() => setSelected(new Set()), [pending?.fetched_at]);

  const sync = useMutation({
    mutationFn: () => siteProfilesApi.sync(siteId),
    onSuccess: (fresh) => {
      queryClient.setQueryData(changesQueryKey(siteId), fresh);
      queryClient.invalidateQueries({ queryKey: ["site-profiles"] });
    },
    onError: (syncError) => toast({ title: "Could not read backend-ot", description: getErrorMessage(syncError), variant: "destructive" }),
  });
  const approve = useMutation({
    mutationFn: (reviewed: PendingChanges) =>
      siteProfilesApi.approve(siteId, { change_ids: [...selected], fetched_at: reviewed.fetched_at }),
    onSuccess: (version) => {
      toast({
        title: version.version === 1 ? "Site onboarded" : `Approved version ${version.version}`,
        description: `${version.change_ids.length} change(s) approved. The AI uses them now.`,
      });
      queryClient.invalidateQueries({ queryKey: ["site-profiles"] });
    },
    onError: (approveError) => {
      if (statusOf(approveError) === 409) {
        toast({ title: "backend-ot was read again", description: "The list changed since you reviewed it. Review it again.", variant: "destructive" });
        queryClient.invalidateQueries({ queryKey: changesQueryKey(siteId) });
        return;
      }
      toast({ title: "Could not approve", description: getErrorMessage(approveError), variant: "destructive" });
    },
  });

  const groups = useMemo(() => groupByTarget(pending?.changes ?? []), [pending]);
  const allIds = useMemo(() => (pending?.changes ?? []).map(change => change.change_id), [pending]);
  const problem = approvalProblem(selected, onboarded);

  const readButton = (
    <Button variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending}>
      <RefreshCw className={`w-4 h-4 mr-2 ${sync.isPending ? "animate-spin" : ""}`} />
      Read backend-ot now
    </Button>
  );

  if (isLoading) return <p className="text-muted-foreground">Loading pending changes...</p>;
  if (isError && statusOf(error) === 404) {
    return (
      <div className="space-y-3">
        <p className="text-muted-foreground">This site hasn't been read from backend-ot yet.</p>
        {readButton}
      </div>
    );
  }
  if (isError || !pending) return <p className="text-destructive">Could not load the pending changes: {getErrorMessage(error)}</p>;

  const toggle = (changeId: string, checked: boolean) => setSelected(current => {
    const next = new Set(current);
    if (checked) next.add(changeId); else next.delete(changeId);
    return next;
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          backend-ot read {formatDateTime(pending.fetched_at, timeZone)} · {pending.changes.length} change(s)
          {!onboarded && pending.changes.length > 0 && " · approving onboards the site for the AI"}
        </p>
        {readButton}
      </div>

      {pending.changes.length === 0 && (
        <p className="text-muted-foreground">Nothing to review: the AI's profile matches backend-ot.</p>
      )}

      {pending.changes.length > 0 && (
        <>
          <HideOnPhone note={EDIT_ON_LARGER_SCREEN}>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set(allIds))}>Select all</Button>
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>Select none</Button>
              <Button onClick={() => approve.mutate(pending)} disabled={problem !== null || approve.isPending}>
                <CheckCheck className="w-4 h-4 mr-2" />
                Approve selected ({selected.size})
              </Button>
              {problem && selected.size > 0 && <span className="text-sm text-destructive">{problem}</span>}
            </div>
          </HideOnPhone>

          {groups.map(group => (
            <section key={group.target} className="rounded-md border">
              <h3 className="px-3 py-2 border-b text-sm font-semibold">
                {CHANGE_TARGET_LABELS[group.target]} <span className="text-muted-foreground font-normal">({group.changes.length})</span>
              </h3>
              <ul className="divide-y max-h-[28rem] overflow-y-auto">
                {group.changes.map(change => (
                  <li key={change.change_id} className="flex items-start gap-3 px-3 py-2">
                    <Checkbox
                      id={`change-${change.change_id}`}
                      checked={selected.has(change.change_id)}
                      onCheckedChange={checked => toggle(change.change_id, checked === true)}
                      aria-label={`Select ${change.summary}`}
                      className="mt-0.5"
                    />
                    <label htmlFor={`change-${change.change_id}`} className="flex-1 min-w-0 cursor-pointer">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className={KIND_STYLES[change.kind]}>{CHANGE_KIND_LABELS[change.kind]}</Badge>
                        <span className="break-words">{change.summary}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{change.change_id}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
