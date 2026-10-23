import { describe, expect, it } from 'vitest';
import type { BackendPointReadings } from '@/api/types/historian';
import { buildChartRows, buildLineSeries } from '@/features/historian/sampling/chartRows';

const readings = (series: Record<string, Array<[string, number | null]>>) => (({
  readings: Object.fromEntries(Object.entries(series).map(([pointId, samples]) => [
    pointId,
    { timeseries: samples.map(([time, value]) => ({ time, value })) },
  ])),
}) as unknown as BackendPointReadings).readings;

describe('a seconds-level point next to a 15-minute forecast', () => {
  it('keeps every reading of the point and only the forecast samples of the forecast', () => {
    const start = Date.parse('2026-10-21T12:00:00Z');
    const point = {
      id: 7, name: 'pv1-W', data_type: 'float32', count: 0,
      timeseries: Array.from({ length: 900 }, (_, index) => ({ time: new Date(start + index * 1000).toISOString(), value: index })),
    };
    const forecast = {
      id: 0, name: 'forecast', data_type: 'float32', count: 0,
      timeseries: [
        { time: '2026-10-21T12:00:00Z', value: 1000 },
        { time: '2026-10-21T12:15:00Z', value: 1000 },
      ],
    };
    const maps = [{ '7': point }, { 'fc:site:pv_ac_kw': forecast }];
    const lines = buildLineSeries(maps, ['7', 'fc:site:pv_ac_kw']);
    expect(lines['7']).toHaveLength(900); // every second kept
    expect(lines['fc:site:pv_ac_kw']).toHaveLength(2);
    const rows = buildChartRows(maps, ['7', 'fc:site:pv_ac_kw']);
    expect(rows.filter(row => row['7'] !== undefined)).toHaveLength(900);
    expect(rows.filter(row => row['fc:site:pv_ac_kw'] !== undefined)).toHaveLength(2);
  });
});

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

describe('buildChartRows with gap markers', () => {
  it('leaves gap markers (no value) out of the rows', () => {
    const rows = buildChartRows(
      [readings({ '4': [['2026-09-27T10:00:00Z', 1], ['2026-09-27T10:05:00Z', null], ['2026-09-27T10:10:00Z', 2]] })],
      ['4'],
    );
    expect(rows.map(row => row['4'])).toEqual([1, 2]);
  });
});

describe('buildLineSeries', () => {
  it('gives each selection every one of its samples, oldest first, keyed by its id', () => {
    const lines = buildLineSeries(
      [
        readings({ '4': [['2026-09-27T10:00:20Z', 2], ['2026-09-27T10:00:00Z', 1]] }),
        readings({ 'fn:site-energy-series': [['2026-09-27T10:00:07Z', 0.5]] }),
      ],
      ['4', 'fn:site-energy-series'],
    );
    expect(lines['4']).toEqual([
      { timestamp: Date.parse('2026-09-27T10:00:00Z'), '4': 1 },
      { timestamp: Date.parse('2026-09-27T10:00:20Z'), '4': 2 },
    ]);
    expect(lines['fn:site-energy-series']).toEqual([{ timestamp: Date.parse('2026-09-27T10:00:07Z'), 'fn:site-energy-series': 0.5 }]);
  });

  it('keeps gap markers as null so the line breaks there', () => {
    const lines = buildLineSeries([readings({ '4': [['2026-09-27T10:00:00Z', 1], ['2026-09-27T10:05:00Z', null]] })], ['4']);
    expect(lines['4'].map(point => point['4'])).toEqual([1, null]);
  });

  it('decodes a bit selection and keeps every sample of a dense series', () => {
    const samples: Array<[string, number]> = Array.from({ length: 26_000 }, (_, index) => [new Date(Date.UTC(2026, 8, 27) + index * 10_000).toISOString(), index % 4]);
    const lines = buildLineSeries([readings({ '12': samples })], ['12', '12:bit1']);
    expect(lines['12']).toHaveLength(26_000);
    expect(lines['12:bit1'].slice(0, 4).map(point => point['12:bit1'])).toEqual([0, 0, 1, 1]);
  });

  it('gives a selection without data an empty line', () => {
    expect(buildLineSeries([], ['4'])).toEqual({ '4': [] });
  });
});
