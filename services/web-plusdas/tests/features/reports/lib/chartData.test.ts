import { describe, expect, it } from 'vitest';
import { seriesLabel, toBarRows, toSamples } from '@/features/reports/lib/chartData';

const series = (id: number, samples: Array<[string, number | null]>, unit: string | null = 'kW') => ({
  id, name: `point_${id}`, data_type: 'float32', unit, count: samples.length,
  timeseries: samples.map(([time, value]) => ({ time, value })),
});

describe('toSamples', () => {
  it('keeps gaps as null values', () => {
    expect(toSamples(series(1, [['2026-10-13T00:00:00Z', 1], ['2026-10-13T00:01:00Z', null]]))).toEqual([
      { time: Date.parse('2026-10-13T00:00:00Z'), value: 1 },
      { time: Date.parse('2026-10-13T00:01:00Z'), value: null },
    ]);
  });
});

describe('toBarRows', () => {
  it('merges series by time, one key per series, oldest first', () => {
    const rows = toBarRows([
      series(1, [['2026-10-13T01:00:00Z', 2]]),
      series(2, [['2026-10-13T00:00:00Z', 5], ['2026-10-13T01:00:00Z', 3]]),
    ]);
    expect(rows).toEqual([
      { time: Date.parse('2026-10-13T00:00:00Z'), s1: 5 },
      { time: Date.parse('2026-10-13T01:00:00Z'), s0: 2, s1: 3 },
    ]);
  });
});

describe('seriesLabel', () => {
  it('adds the unit when there is one', () => {
    expect(seriesLabel(series(1, []))).toBe('point_1 (kW)');
    expect(seriesLabel(series(1, [], null))).toBe('point_1');
  });
});
