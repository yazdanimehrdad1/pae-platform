import type { AlarmEventsTableResult, PointStatsTableResult } from "@/api/types/reports";
import { formatReportTime, STAT_LABELS } from "./format";

type Cell = string | number | null | undefined;

/** RFC 4180: cells with a comma, quote or line break are quoted, quotes doubled; CRLF line ends. */
export function toCsv(rows: Cell[][]): string {
  return rows
    .map(row => row.map(cell => {
      const text = cell === null || cell === undefined ? "" : String(cell);
      return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    }).join(","))
    .join("\r\n");
}

/** Save text as a file the browser downloads (nothing is sent anywhere). */
export function downloadFile(fileName: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** "daily_energy-hourly.csv": lower-case words joined by '-' or '_', nothing else. */
export function fileName(...parts: string[]): string {
  return parts
    .map(part => part.toLowerCase().replace(/[^a-z0-9_]+/g, "-").replace(/^-+|-+$/g, ""))
    .filter(Boolean)
    .join("-");
}

/** Times in the site's zone, as shown; values unformatted, so a spreadsheet can compute with them. */
export function pointStatsCsv(block: PointStatsTableResult, timeZone: string): string {
  const stats = block.stats ?? [];
  const bucketed = block.bucket !== "none";
  const header = ["Point", "Device", ...(bucketed ? [`${block.bucket === "hour" ? "Hour" : "Day"} (${timeZone})`] : []), "Unit", ...stats.map(stat => STAT_LABELS[stat])];
  const rows = (block.rows ?? []).map(row => [
    row.point_name,
    row.device_name,
    ...(bucketed ? [row.bucket_start ? formatReportTime(row.bucket_start, timeZone) : ""] : []),
    row.unit,
    ...stats.map(stat => row.values?.[stat]),
  ]);
  return toCsv([header, ...rows]);
}

export function alarmEventsCsv(block: AlarmEventsTableResult, timeZone: string): string {
  const header = ["Alarm", "Severity", "Device", `Raised (${timeZone})`, `Cleared (${timeZone})`, "Duration (s)", "Value at raise", "Message"];
  const rows = (block.rows ?? []).map(row => [
    row.alarm_name,
    row.severity,
    row.device_name,
    formatReportTime(row.raised_at, timeZone),
    row.cleared_at ? formatReportTime(row.cleared_at, timeZone) : "",
    row.duration_seconds,
    row.value_at_raise,
    row.message,
  ]);
  return toCsv([header, ...rows]);
}
