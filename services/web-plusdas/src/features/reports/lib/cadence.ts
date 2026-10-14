import type { ReportCadence } from "@/api/types/reports";

// A schedule's cadence (always on the site's clock) and retention, in words, and blank cadences
// for the schedule form. backend-ot works out the actual times.

export type CadenceKind = ReportCadence["kind"];

export const CADENCE_KIND_LABELS: Record<CadenceKind, string> = {
  hourly: "Every hour",
  daily: "Every day",
  weekly: "Every week",
  monthly: "Every month",
};

/** Monday first, as backend-ot numbers them (0 = Monday ... 6 = Sunday). */
export const WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function defaultCadence(kind: CadenceKind): ReportCadence {
  switch (kind) {
    case "hourly":
      return { kind, minute: 0 };
    case "daily":
      return { kind, time: "06:00" };
    case "weekly":
      return { kind, time: "06:00", weekdays: [0] };
    case "monthly":
      return { kind, time: "06:00", day_of_month: 1 };
  }
}

function listOf(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** "Every day at 06:00", "Every Monday and Friday at 07:30", "On day 1 of every month at 05:00". */
export function describeCadence(cadence: ReportCadence): string {
  switch (cadence.kind) {
    case "hourly":
      return `Every hour at :${String(cadence.minute ?? 0).padStart(2, "0")}`;
    case "daily":
      return `Every day at ${cadence.time}`;
    case "weekly": {
      const days = [...cadence.weekdays].sort((first, second) => first - second);
      if (days.length === 7) return `Every day at ${cadence.time}`;
      if (days.join() === "0,1,2,3,4") return `Every weekday at ${cadence.time}`;
      return `Every ${listOf(days.map(day => WEEKDAY_NAMES[day]))} at ${cadence.time}`;
    }
    case "monthly":
      return `On day ${cadence.day_of_month} of every month at ${cadence.time}`;
  }
}

/** "Keeps the last 7 reports", "Keeps 30 days", "Keeps the last 7, at most 30 days", "Keeps every report". */
export function describeRetention(keepLast: number | null | undefined, keepDays: number | null | undefined): string {
  const last = keepLast ? `the last ${keepLast} report${keepLast === 1 ? "" : "s"}` : null;
  const days = keepDays ? `${keepDays} day${keepDays === 1 ? "" : "s"}` : null;
  if (last && days) return `Keeps ${last}, at most ${days} old`;
  if (last) return `Keeps ${last}`;
  if (days) return `Keeps ${days}`;
  return "Keeps every report";
}
