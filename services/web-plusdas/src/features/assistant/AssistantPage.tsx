import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { MessageSquarePlus, Send } from "lucide-react";
import { assistantApi } from "@/api/assistant";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { TimeZoneToggle } from "@/shared/components/TimeZoneToggle";
import { useDisplayTimeZone } from "@/shared/hooks/useDisplayTimeZone";
import { PREFERENCE_KEYS, usePreference } from "@/shared/hooks/usePreference";
import { ConversationItem } from "./components/ConversationItem";
import { TurnView } from "./components/TurnView";
import { ASSISTANT_SITES_QUERY_KEY, conversationQueryKey, conversationsQueryKey } from "./queryKeys";

// Ask the AI about one site. The AI reads the site's data when asked (approved points only),
// and every conversation is saved for the user: the list on the left reopens, renames or
// permanently deletes one. Only the sites the user may access are offered. The sidebar's "Ask AI Assistant..." box opens this page with
// ?q=<question> and asks it.

const SELECT_CLASS = "flex h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

const isString = (value: unknown): value is string => typeof value === "string";

const AssistantPage = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [lastSite, setLastSite] = usePreference<string>(PREFERENCE_KEYS.lastSite, "", isString);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const transcriptEnd = useRef<HTMLDivElement>(null);

  const sites = useQuery({ queryKey: ASSISTANT_SITES_QUERY_KEY, queryFn: assistantApi.sites });
  const site = sites.data?.find(entry => String(entry.site_id) === lastSite) ?? sites.data?.[0] ?? null;
  const siteId = site?.site_id ?? null;
  const { timeZone, display, setDisplay, siteTimeZone } = useDisplayTimeZone(site?.timezone);

  const conversations = useQuery({
    queryKey: conversationsQueryKey(siteId),
    queryFn: () => assistantApi.conversations(siteId ?? undefined),
    enabled: siteId !== null,
  });
  const conversation = useQuery({
    queryKey: conversationQueryKey(conversationId ?? ""),
    queryFn: () => assistantApi.conversation(conversationId ?? ""),
    enabled: conversationId !== null,
  });

  const ask = useMutation({
    mutationFn: (text: string) => {
      if (siteId === null) throw new Error("Choose a site first");
      return assistantApi.ask(siteId, { question: text, conversation_id: conversationId });
    },
    onMutate: text => setPendingQuestion(text),
    // The box empties when the question is sent (submit); it comes back only if the ask fails
    // and the user hasn't started typing another one.
    onError: (_error, text) => setQuestion(current => current || text),
    onSuccess: async answer => {
      setConversationId(answer.conversation_id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: conversationQueryKey(answer.conversation_id) }),
        queryClient.invalidateQueries({ queryKey: ["assistant", "conversations"] }),
      ]);
    },
    onSettled: () => setPendingQuestion(null),
  });

  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => assistantApi.rename(id, { title }),
    onSuccess: (_summary, { id }) => Promise.all([
      queryClient.invalidateQueries({ queryKey: ["assistant", "conversations"] }),
      queryClient.invalidateQueries({ queryKey: conversationQueryKey(id) }),
    ]),
  });
  const remove = useMutation({
    mutationFn: (id: string) => assistantApi.remove(id),
    onSuccess: (_nothing, id) => {
      if (id === conversationId) setConversationId(null);
      queryClient.removeQueries({ queryKey: conversationQueryKey(id) });
      return queryClient.invalidateQueries({ queryKey: ["assistant", "conversations"] });
    },
  });
  const listError = rename.error ?? remove.error;

  // The sidebar's box: ask its question once the site is known, then drop it from the URL.
  const sidebarQuestion = searchParams.get("q");
  useEffect(() => {
    if (!sidebarQuestion || siteId === null || ask.isPending) return;
    setSearchParams({}, { replace: true });
    setConversationId(null);
    ask.mutate(sidebarQuestion);
  }, [sidebarQuestion, siteId, ask, setSearchParams]);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView?.({ block: "end" });
  }, [conversation.data, pendingQuestion]);

  const chooseSite = (value: string) => {
    setLastSite(value);
    setConversationId(null);
  };
  const submit = () => {
    const text = question.trim();
    if (!text || ask.isPending) return;
    setQuestion("");
    ask.mutate(text);
  };
  const turns = conversationId !== null ? conversation.data?.turns ?? [] : [];

  return (
    <div className="flex h-full flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">AI Assistant</h1>
          <p className="text-muted-foreground mt-1">
            Ask about one site. The AI reads the site's live data when you ask; your conversations are saved.
          </p>
        </div>
        <TimeZoneToggle siteTimeZone={siteTimeZone} display={display} onDisplayChange={setDisplay} />
      </div>

      {sites.isError && <p role="alert" className="text-sm text-destructive">{getErrorMessage(sites.error)}</p>}
      {sites.isSuccess && sites.data.length === 0 && (
        <p className="text-sm text-muted-foreground">You have no site to ask about.</p>
      )}

      {site && (
        <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-[16rem_1fr]">
          <aside className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="assistant-site">Site</Label>
              <select id="assistant-site" className={SELECT_CLASS} value={String(site.site_id)} onChange={event => chooseSite(event.target.value)}>
                {sites.data?.map(entry => <option key={entry.site_id} value={entry.site_id}>{entry.name}</option>)}
              </select>
            </div>
            <Button variant="outline" size="sm" className="w-full" onClick={() => setConversationId(null)}>
              <MessageSquarePlus className="w-4 h-4 mr-1" />New conversation
            </Button>
            <nav aria-label="Conversations" className="space-y-1">
              {conversations.data?.length === 0 && <p className="text-xs text-muted-foreground">No conversations yet.</p>}
              {listError && <p role="alert" className="text-xs text-destructive">{getErrorMessage(listError)}</p>}
              {conversations.data?.map(summary => (
                <ConversationItem
                  key={summary.conversation_id}
                  summary={summary}
                  isOpen={summary.conversation_id === conversationId}
                  timeZone={timeZone}
                  onOpen={() => setConversationId(summary.conversation_id)}
                  onRename={title => { remove.reset(); rename.mutate({ id: summary.conversation_id, title }); }}
                  onDelete={() => { rename.reset(); remove.mutate(summary.conversation_id); }}
                />
              ))}
            </nav>
          </aside>

          <section className="flex min-h-[24rem] flex-col rounded-lg border bg-card">
            <div className="flex-1 space-y-6 overflow-y-auto p-4" aria-label="Conversation">
              {turns.length === 0 && pendingQuestion === null && (
                <p className="text-sm text-muted-foreground">
                  Ask about {site.name}: alarms, a device's state, what happened at a given time, energy and more.
                </p>
              )}
              {conversationId !== null && turns.map(turn => (
                <TurnView key={turn.turn_id} conversationId={conversationId} turn={turn} timeZone={timeZone} />
              ))}
              {pendingQuestion !== null && (
                <div className="space-y-2">
                  <div className="ml-auto max-w-[85%] rounded-lg bg-primary/10 px-3 py-2 text-sm whitespace-pre-wrap">{pendingQuestion}</div>
                  <p className="text-sm text-muted-foreground" role="status">Thinking... the AI is reading the site's data.</p>
                </div>
              )}
              {ask.isError && <p role="alert" className="text-sm text-destructive">{getErrorMessage(ask.error)}</p>}
              <div ref={transcriptEnd} />
            </div>
            <form
              className="flex items-end gap-2 border-t p-3"
              onSubmit={event => { event.preventDefault(); submit(); }}
            >
              <Textarea
                aria-label="Your question"
                placeholder={`Ask about ${site.name}...`}
                value={question}
                maxLength={8000}
                rows={2}
                onChange={event => setQuestion(event.target.value)}
                onKeyDown={event => {
                  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); }
                }}
              />
              <Button type="submit" disabled={ask.isPending || !question.trim()}>
                <Send className="w-4 h-4 mr-1" />Ask
              </Button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
};

export default AssistantPage;
