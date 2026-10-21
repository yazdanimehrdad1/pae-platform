import type { TimeRange } from '@/api/types/historian';
import type { TimeWindow } from '../types';

// How far back each preset reaches (backend-ot resolves presets to a window ending now).
export const PRESET_MS: Record<TimeRange, number> = {
  '1H': 3_600_000, '6H': 6 * 3_600_000, '12H': 12 * 3_600_000,
  '1D': 24 * 3_600_000, '2D': 48 * 3_600_000, '3D': 72 * 3_600_000,
  '1W': 7 * 24 * 3_600_000, '1M': 30 * 24 * 3_600_000, '3M': 90 * 24 * 3_600_000,
};

// "Forecast ahead" choices: how far past now a preset window's forecast reaches.
export const FORECAST_AHEAD_HOURS = [0, 24, 48, 72] as const;
export type ForecastAheadHours = (typeof FORECAST_AHEAD_HOURS)[number];

// The forecast keeps 7 days of history and intelli-gateway serves at most 11 days at once: a longer
// window asks for its last 10 days only (nothing older is stored anyway).
const MAX_FORECAST_SPAN_MS = 10 * 24 * 3_600_000;

/** The forecast's window for a chart: a preset reaches back from now and `aheadHours` past it;
 * a custom range (or a zoom) is used as given, and may itself end in the future. At most the
 * window's last 10 days. */
export function forecastRange(
  timeWindow: TimeWindow,
  aheadHours: number,
  now: number = Date.now(),
): { start: string; end: string } {
  const [start, end] = 'preset' in timeWindow
    ? [now - PRESET_MS[timeWindow.preset], now + aheadHours * 3_600_000]
    : [new Date(timeWindow.startTime).getTime(), new Date(timeWindow.endTime).getTime()];
  return {
    start: new Date(Math.max(start, end - MAX_FORECAST_SPAN_MS)).toISOString(),
    end: new Date(end).toISOString(),
  };
}
