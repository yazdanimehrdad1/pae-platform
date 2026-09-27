import type { TimeRange } from '@/api/types/historian';

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
}
