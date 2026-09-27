import { CircleCheck } from "lucide-react";
import { formatSiteTime } from "../lib/siteTime";
import type { AlarmLogEntry } from "../types";
import { SeverityIndicator } from "./SeverityIndicator";

/** Raise and clear entries, newest first. */
export function EventLog({ entries, timeZone }: { entries: AlarmLogEntry[]; timeZone: string }) {
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">No events in the last 6 h.</p>;
  return (
    <ol className="divide-y divide-border text-sm">
      {entries.map(entry => (
        <li key={entry.id} className="flex items-baseline gap-3 py-1.5">
          <time dateTime={entry.at} className="w-32 shrink-0 tabular-nums text-muted-foreground">
            {formatSiteTime(entry.at, timeZone)}
          </time>
          {entry.kind === "raised" ? (
            <SeverityIndicator severity={entry.severity} className="w-24" />
          ) : (
            <span className="inline-flex w-24 items-center gap-1.5 text-muted-foreground">
              <CircleCheck aria-hidden className="h-4 w-4" />Cleared
            </span>
          )}
          <span className="min-w-0 flex-1">{entry.message}</span>
        </li>
      ))}
    </ol>
  );
}
