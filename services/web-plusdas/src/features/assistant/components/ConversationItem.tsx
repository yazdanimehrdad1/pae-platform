import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import type { ConversationSummary } from "@/api/types/assistant";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { formatSiteTime } from "@/shared/lib/siteTime";

// One saved conversation in the assistant's list: open it, rename it in place (Enter saves,
// Escape or leaving the box cancels), or delete it for good after a confirmation.

const TITLE_MAX = 200;

interface ConversationItemProps {
  summary: ConversationSummary;
  isOpen: boolean;
  timeZone: string;
  onOpen: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}

export function ConversationItem({ summary, isOpen, timeZone, onOpen, onRename, onDelete }: ConversationItemProps) {
  const [draftTitle, setDraftTitle] = useState<string | null>(null);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);

  const saveTitle = () => {
    const title = (draftTitle ?? "").split(/\s+/).filter(Boolean).join(" ");
    setDraftTitle(null);
    if (title && title !== summary.title) onRename(title);
  };

  if (draftTitle !== null) {
    return (
      <Input
        autoFocus
        aria-label="Conversation name"
        value={draftTitle}
        maxLength={TITLE_MAX}
        className="h-8 text-sm"
        onChange={event => setDraftTitle(event.target.value)}
        onBlur={() => setDraftTitle(null)}
        onKeyDown={event => {
          if (event.key === "Enter") { event.preventDefault(); saveTitle(); }
          if (event.key === "Escape") { event.preventDefault(); setDraftTitle(null); }
        }}
      />
    );
  }

  return (
    <div className={cn("group flex items-start gap-1 rounded-md hover:bg-accent", isOpen && "bg-accent")}>
      <button
        type="button"
        aria-current={isOpen ? "true" : undefined}
        onClick={onOpen}
        className="min-w-0 flex-1 px-2 py-1.5 text-left text-sm"
      >
        <span className="block truncate">{summary.title}</span>
        <span className="block text-xs text-muted-foreground">
          {formatSiteTime(summary.updated_at, timeZone, { withDate: true })} · {summary.turns} {summary.turns === 1 ? "question" : "questions"}
        </span>
      </button>
      <div className="flex shrink-0 gap-0.5 py-1 pr-1 transition-opacity [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:group-focus-within:opacity-100">
        <button
          type="button"
          aria-label={`Rename ${summary.title}`}
          title="Rename"
          onClick={() => setDraftTitle(summary.title)}
          className="rounded p-1 text-muted-foreground hover:bg-background hover:text-foreground"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label={`Delete ${summary.title}`}
          title="Delete"
          onClick={() => setIsConfirmingDelete(true)}
          className="rounded p-1 text-muted-foreground hover:bg-background hover:text-destructive"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <AlertDialog open={isConfirmingDelete} onOpenChange={setIsConfirmingDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              "{summary.title}" and all its questions and answers are deleted permanently. This can't be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={onDelete}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
