import { describe, expect, it } from 'vitest';
import type { LinePoint } from '@/features/historian/sampling/chartRows';
import { latestAtOrBefore } from '@/features/historian/sampling/tooltip';

const line = (points: Array<[number, number | null]>): LinePoint[] =>
  points.map(([timestamp, value]) => ({ timestamp, p: value }) as LinePoint);

describe('latestAtOrBefore', () => {
  const points = line([[10, 1], [20, 2], [30, null], [40, 4]]);

  it('is the latest sample at or before the hovered time', () => {
    expect(latestAtOrBefore(points, 'p', 20)).toBe(2);
    expect(latestAtOrBefore(points, 'p', 25)).toBe(2);
    expect(latestAtOrBefore(points, 'p', 99)).toBe(4);
  });

  it('is null before the first sample and inside an outage', () => {
    expect(latestAtOrBefore(points, 'p', 5)).toBeNull();
    expect(latestAtOrBefore(points, 'p', 35)).toBeNull();
    expect(latestAtOrBefore([], 'p', 35)).toBeNull();
  });
});
