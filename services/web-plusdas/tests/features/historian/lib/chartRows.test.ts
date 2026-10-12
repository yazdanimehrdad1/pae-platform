import { describe, expect, it } from 'vitest';
import type { BackendPointReadings } from '@/api/types/historian';
import { buildChartRows } from '@/features/historian/lib/chartRows';

const readings = (series: Record<string, Array<[string, number | null]>>) => (({
  readings: Object.fromEntries(Object.entries(series).map(([pointId, samples]) => [
    pointId,
    { timeseries: samples.map(([time, value]) => ({ time, value })) },
  ])),
}) as unknown as BackendPointReadings).readings;

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

describe('buildChartRows with function series', () => {
  it('merges a function series, keyed by its selection id, with point readings on shared timestamps', () => {
    const rows = buildChartRows(
      [readings({ '4': [['2026-09-27T10:00:00Z', 1]] }), readings({ 'fn:site-poi-power': [['2026-09-27T10:00:00Z', 250], ['2026-09-27T10:01:00Z', 260]] })],
      ['4', 'fn:site-poi-power'],
    );
    expect(rows).toEqual([
      { timestamp: Date.parse('2026-09-27T10:00:00Z'), '4': 1, 'fn:site-poi-power': 250 },
      { timestamp: Date.parse('2026-09-27T10:01:00Z'), 'fn:site-poi-power': 260 },
    ]);
  });
});

describe('buildChartRows across devices', () => {
  it("puts one poll cycle's readings from different devices in one row, at the cycle's last time", () => {
    const rows = buildChartRows(
      [
        readings({ '4': [['2026-09-27T10:00:00.522Z', 1], ['2026-09-27T10:00:20.511Z', 2]] }),
        readings({ '9': [['2026-09-27T10:00:00.516Z', 10], ['2026-09-27T10:00:20.569Z', 20]] }),
      ],
      ['4', '9'],
    );
    expect(rows).toEqual([
      { timestamp: Date.parse('2026-09-27T10:00:00.522Z'), '4': 1, '9': 10 },
      { timestamp: Date.parse('2026-09-27T10:00:20.569Z'), '4': 2, '9': 20 },
    ]);
  });

  it('keeps readings further apart than the tolerance in separate rows', () => {
    const rows = buildChartRows(
      [readings({ '4': [['2026-09-27T10:00:00.000Z', 1]], '9': [['2026-09-27T10:00:01.000Z', 10]] })],
      ['4', '9'],
    );
    expect(rows.map(row => Object.keys(row).filter(key => key !== 'timestamp'))).toEqual([['4'], ['9']]);
  });

  it('gives a series sampled twice within the tolerance two rows instead of overwriting', () => {
    const rows = buildChartRows(
      [readings({ '4': [['2026-09-27T10:00:00.000Z', 1], ['2026-09-27T10:00:00.400Z', 2]] })],
      ['4'],
    );
    expect(rows.map(row => row['4'])).toEqual([1, 2]);
  });

  it('keeps each series at its own rate, so a missing poll leaves a gap in that column only', () => {
    const rows = buildChartRows(
      [
        readings({ '4': [['2026-09-27T10:00:00Z', 1], ['2026-09-27T10:00:20Z', 2], ['2026-09-27T10:00:40Z', 3]] }),
        readings({ 'fn:site-energy-series': [['2026-09-27T10:00:00.3Z', 0], ['2026-09-27T10:00:40.3Z', 0.5]] }),
      ],
      ['4', 'fn:site-energy-series'],
    );
    expect(rows.map(row => [row['4'], row['fn:site-energy-series']])).toEqual([[1, 0], [2, undefined], [3, 0.5]]);
  });

  it('ignores series nobody selected', () => {
    expect(buildChartRows([readings({ '7': [['2026-09-27T10:00:00Z', 1]] })], ['4'])).toEqual([]);
  });
});
