import { CircleAlert, CircleCheck, Clock, Loader2 } from "lucide-react";
import type { ReportRunStatus } from "@/api/types/reports";
import { cn } from "@/lib/utils";
import { STATUS_LABELS } from "../lib/format";

const STATUS_STYLE: Record<ReportRunStatus, { Icon: typeof Clock; className: string; spin?: boolean }> = {
  queued: { Icon: Clock, className: "text-muted-foreground" },
  running: { Icon: Loader2, className: "text-muted-foreground", spin: true },
  succeeded: { Icon: CircleCheck, className: "text-foreground" },
  failed: { Icon: CircleAlert, className: "text-destructive" },
};

/** A run's state as icon + word (never color alone). */
export function RunStatusBadge({ status }: { status: ReportRunStatus }) {
  const { Icon, className, spin } = STATUS_STYLE[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm", className)}>
      <Icon aria-hidden className={cn("h-4 w-4 shrink-0", spin && "animate-spin")} />
      {STATUS_LABELS[status]}
    </span>
  );
}
