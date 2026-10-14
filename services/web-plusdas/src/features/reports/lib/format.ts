import type { PointStat, ReportRunStatus, ReportWindow } from "@/api/types/reports";

// Report times are shown in the site's time zone (the one the report was generated in).

const dateTimeFormatters = new Map<string, Intl.DateTimeFormat>();

/** "13 Oct 2026, 15:27". */
export function formatReportTime(at: string | number, timeZone: string): string {
  let formatter = dateTimeFormatters.get(timeZone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-GB", {
      timeZone, day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
    });
    dateTimeFormatters.set(timeZone, formatter);
  }
  return formatter.format(new Date(at));
}

/** "13 Oct 2026, 00:00 – 14 Oct 2026, 00:00". */
export function formatWindow(start: string, end: string, timeZone: string): string {
  return `${formatReportTime(start, timeZone)} – ${formatReportTime(end, timeZone)}`;
}

/** Fewer decimals for bigger numbers: 1 234, 12.35, 0.123. Null is a dash. */
export function formatValue(value: number | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const magnitude = Math.abs(value);
  const maximumFractionDigits = magnitude >= 100 ? 0 : magnitude >= 1 ? 2 : 3;
  const text = value.toLocaleString("en-US", { maximumFractionDigits });
  return unit ? `${text} ${unit}` : text;
}

export const STAT_LABELS: Record<PointStat, string> = {
  min: "Min",
  max: "Max",
  avg: "Average",
  first: "First",
  last: "Last",
  count: "Samples",
};

export const STATUS_LABELS: Record<ReportRunStatus, string> = {
  queued: "Queued",
  running: "Generating",
  succeeded: "Ready",
  failed: "Failed",
};

/** A run that the worker hasn't finished yet. */
export function isPending(status: ReportRunStatus): boolean {
  return status === "queued" || status === "running";
}

const ROLLING_LABELS: Record<Extract<ReportWindow, { kind: "rolling" }>["duration"], string> = {
  "1H": "Last hour",
  "6H": "Last 6 hours",
  "12H": "Last 12 hours",
  "1D": "Last 24 hours",
  "2D": "Last 2 days",
  "3D": "Last 3 days",
  "1W": "Last 7 days",
  "1M": "Last 30 days",
  "3M": "Last 90 days",
};

const PERIOD_NAMES = { day: ["Today", "Yesterday", "day"], week: ["This week", "Last week", "week"], month: ["This month", "Last month", "month"] } as const;

/** What a definition's window covers, in words ("Yesterday", "Last 7 days", "Fixed range"). */
export function windowLabel(window: ReportWindow): string {
  switch (window.kind) {
    case "rolling":
      return ROLLING_LABELS[window.duration];
    case "calendar": {
      const [current, previous, unit] = PERIOD_NAMES[window.period];
      const offset = window.offset ?? -1;
      if (offset === 0) return `${current} so far`;
      if (offset === -1) return previous;
      return `${-offset} ${unit}s ago`;
    }
    case "fixed":
      return "Fixed range";
  }
}
