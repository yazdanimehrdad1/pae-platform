import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { knowledgeApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { KnowledgeState } from "@/api/types/knowledge";
import { toast } from "@/shared/hooks/use-toast";
import { isDraftConflict, knowledgeQueryKey } from "./lib";

/** The site's knowledge (the draft, or the published one when there is no draft). */
export function useKnowledge(siteId: number) {
  return useQuery({ queryKey: knowledgeQueryKey(siteId), queryFn: () => knowledgeApi.get(siteId), retry: false });
}

/**
 * One draft edit. The answer is the new state, so the cache takes it as is. On a 409 (someone
 * saved in between) the state is reloaded and the user told; other errors reach the caller.
 */
export function useKnowledgeEdit<Args>(
  siteId: number,
  edit: (args: Args) => Promise<KnowledgeState>,
  { onSaved, onError }: { onSaved?: (state: KnowledgeState) => void; onError?: (message: string) => void } = {},
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: edit,
    onSuccess: (state) => {
      queryClient.setQueryData(knowledgeQueryKey(siteId), state);
      queryClient.invalidateQueries({ queryKey: ["site-profiles", siteId, "knowledge-coverage"] });
      onSaved?.(state);
    },
    onError: (error) => {
      if (isDraftConflict(error)) {
        queryClient.invalidateQueries({ queryKey: knowledgeQueryKey(siteId) });
        toast({ title: "The draft changed", description: "Someone saved in between. It was reloaded: check it and try again.", variant: "destructive" });
        return;
      }
      const message = getErrorMessage(error);
      if (onError) onError(message);
      else toast({ title: "Could not save", description: message, variant: "destructive" });
    },
  });
}
