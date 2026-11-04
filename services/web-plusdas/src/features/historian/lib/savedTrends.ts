import type { SavedTrend, TrendDefinition } from "@/api/types/me";
import type { Trend } from "../types";
import { isAxisScale } from "./axes";
import { sanitizeSeriesStyles } from "./seriesStyles";

// A trend as the UI uses it (features/historian/types.ts) and as intelli-gateway stores it for
// the user: only its definition (name, point selection ids, axis scale, line styles), never readings.

/** A trend read from the server or from old browser storage: a scale this version doesn't know is
 * dropped (it shows per unit), and so are invalid styles (those lines get their default look). */
export function toTrend(raw: { id: string | number; name: string; points?: unknown; scale?: unknown; styles?: unknown }): Trend {
  const points = Array.isArray(raw.points) ? raw.points.filter((point): point is string => typeof point === "string") : [];
  const trend: Trend = { id: String(raw.id), name: raw.name, points };
  if (isAxisScale(raw.scale)) trend.scale = raw.scale;
  const styles = sanitizeSeriesStyles(raw.styles);
  if (styles) trend.styles = styles;
  return trend;
}

export function fromSavedTrend(saved: SavedTrend): Trend {
  return toTrend(saved);
}

export function toDefinition(trend: Trend): TrendDefinition {
  return { name: trend.name, points: trend.points, scale: trend.scale ?? null, styles: trend.styles ?? null };
}

export function sameDefinition(first: Trend, second: Trend): boolean {
  return JSON.stringify(toDefinition(first)) === JSON.stringify(toDefinition(second));
}

/** Trends saved in this browser before they moved to the server (`historian_trends_<user>` in
 * localStorage): the valid ones, for the one-time import. */
export function parseLegacyTrends(stored: string | null): Trend[] {
  if (!stored) return [];
  try {
    const parsed: unknown = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((raw): raw is { id: string; name: string } =>
        typeof raw === "object" && raw !== null && typeof raw.name === "string" && raw.name.trim() !== "")
      .map(raw => toTrend({ ...raw, id: String(raw.id ?? "") }));
  } catch {
    return [];
  }
}
