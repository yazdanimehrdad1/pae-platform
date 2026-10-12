import type { LinePoint } from './chartRows';

// A line's value at a hovered time: its latest sample at or before that time (binary search over
// the oldest-first samples). Null before its first sample, and null inside an outage (the latest
// sample is a gap marker), so the tooltip never shows a value the line doesn't draw.
export function latestAtOrBefore(points: LinePoint[], selectionId: string, timestamp: number): number | null {
  let low = 0;
  let high = points.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (points[middle].timestamp <= timestamp) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found < 0 ? null : points[found][selectionId] ?? null;
}
