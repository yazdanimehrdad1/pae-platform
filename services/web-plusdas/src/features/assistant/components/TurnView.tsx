import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { assistantApi } from "@/api/assistant";
import { getErrorMessage } from "@/api/client";
import type { AnswerRating, ConversationTurn } from "@/api/types/assistant";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { formatSiteTime } from "@/shared/lib/siteTime";
import { conversationQueryKey } from "../queryKeys";

// One question and the AI's answer: what it read (tools and their arguments, not the values),
// the tokens it used, and the user's 👍 / 👎 with an optional comment.

function tokensText(turn: ConversationTurn): string {
  const usage = turn.usage;
  const parts = [`${usage.input_tokens.toLocaleString()} in`, `${usage.output_tokens.toLocaleString()} out`];
  if (usage.cache_read_input_tokens) parts.push(`${usage.cache_read_input_tokens.toLocaleString()} cached`);
  if (usage.cache_creation_input_tokens) parts.push(`${usage.cache_creation_input_tokens.toLocaleString()} cache write`);
  return `Tokens: ${parts.join(" · ")}`;
}

export function TurnView({ conversationId, turn, timeZone }: {
  conversationId: string;
  turn: ConversationTurn;
  timeZone: string;
}) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState(turn.feedback_comment ?? "");
  const feedback = useMutation({
    mutationFn: (rating: AnswerRating | null) =>
      assistantApi.setFeedback(conversationId, turn.turn_id, { rating, comment: rating ? comment.trim() || null : null }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: conversationQueryKey(conversationId) }),
  });
  const rate = (rating: AnswerRating) => feedback.mutate(turn.feedback === rating ? null : rating);

  return (
    <article className="space-y-2" aria-label={`Answer to: ${turn.question}`}>
      <div className="ml-auto max-w-[85%] rounded-lg bg-primary/10 px-3 py-2 text-sm whitespace-pre-wrap">{turn.question}</div>
      <div className="rounded-lg border bg-card px-3 py-2 text-sm whitespace-pre-wrap">{turn.answer}</div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>{formatSiteTime(turn.created_at, timeZone, { withDate: true })}</span>
        <span>{tokensText(turn)}</span>
        {turn.stop_reason !== "end_turn" && <span className="text-destructive">Stopped: {turn.stop_reason}</span>}
        <span className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost" size="sm" aria-label="Helpful" aria-pressed={turn.feedback === "up"}
            className={cn(turn.feedback === "up" && "text-green-600 dark:text-green-400")}
            disabled={feedback.isPending} onClick={() => rate("up")}
          >
            <ThumbsUp className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost" size="sm" aria-label="Not helpful" aria-pressed={turn.feedback === "down"}
            className={cn(turn.feedback === "down" && "text-destructive")}
            disabled={feedback.isPending} onClick={() => rate("down")}
          >
            <ThumbsDown className="w-4 h-4" />
          </Button>
        </span>
      </div>
      {turn.feedback && (
        <form
          className="flex gap-2"
          onSubmit={event => { event.preventDefault(); if (turn.feedback) feedback.mutate(turn.feedback); }}
        >
          <Input
            aria-label="Feedback comment"
            placeholder={turn.feedback === "down" ? "What was wrong? (optional)" : "Comment (optional)"}
            value={comment}
            maxLength={2000}
            onChange={event => setComment(event.target.value)}
            className="h-8 text-xs"
          />
          <Button type="submit" size="sm" variant="outline" disabled={feedback.isPending}>Save</Button>
        </form>
      )}
      {feedback.isError && <p role="alert" className="text-xs text-destructive">{getErrorMessage(feedback.error)}</p>}
      {turn.tool_calls.length > 0 && (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">What the AI read ({turn.tool_calls.length})</summary>
          <ul className="mt-1 space-y-1">
            {turn.tool_calls.map((call, index) => (
              <li key={index} className={cn("font-mono break-all", call.is_error && "text-destructive")}>
                {call.name}({JSON.stringify(call.args)})
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
