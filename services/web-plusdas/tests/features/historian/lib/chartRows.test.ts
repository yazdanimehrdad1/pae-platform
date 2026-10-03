import { describe, expect, it } from 'vitest';
import type { BackendPointReadings } from '@/api/types/historian';
import { buildChartRows } from '@/features/historian/lib/chartRows';

const readings = (series: Record<string, Array<[string, number | null]>>) => ({
  readings: Object.fromEntries(Object.entries(series).map(([pointId, samples]) => [
    pointId,
    { timeseries: samples.map(([time, value]) => ({ time, value })) },
  ])),
}) as unknown as BackendPointReadings;

describe('buildChartRows', () => {
  it('gives each bit selection its own 0/1 column from one fetched point', () => {
    const rows = buildChartRows(
      [readings({ '12': [['2026-09-27T10:00:00Z', 0b101], ['2026-09-27T10:01:00Z', 0b010]], '4': [['2026-09-27T10:00:00Z', 230.5]] })],
      ['12:bit0', '12:bit1', '4'],
    );

    expect(rows).toEqual([
      { timestamp: Date.parse('2026-09-27T10:00:00Z'), '12:bit0': 1, '12:bit1': 0, '4': 230.5 },
      { timestamp: Date.parse('2026-09-27T10:01:00Z'), '12:bit0': 0, '12:bit1': 1 },
    ]);
  });

  it('skips null readings and sorts by time', () => {
    const rows = buildChartRows(
      [readings({ '4': [['2026-09-27T10:02:00Z', 2], ['2026-09-27T10:01:00Z', null], ['2026-09-27T10:00:00Z', 1]] })],
      ['4'],
    );
    expect(rows.map(row => row['4'])).toEqual([1, 2]);
  });
});
