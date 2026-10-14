import type { TimeRange } from '@/api/types/historian';
import type { AxisScale } from './lib/axes';

// One chart row: `timestamp` plus one value column per selected point.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ChartRow = Record<string, any>;

export type TimeWindow =
  | { preset: TimeRange }
  | { startTime: string; endTime: string };

// A saved set of points, kept in localStorage per user (lib/trendStorage.ts).
export interface Trend {
  id: string;
  name: string;
  points: string[];
  /** How its lines share vertical axes (lib/axes.ts); missing on trends saved before it existed: per unit. */
  scale?: AxisScale;
}
