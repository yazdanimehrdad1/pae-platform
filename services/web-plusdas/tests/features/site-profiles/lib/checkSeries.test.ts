import { describe, expect, it } from 'vitest';
import { checkAgainstBackendOt } from '@/features/site-profiles/lib/checkSeries';

// The admin's "Try it" turns what the AI got back into times and values and compares it with
// backend-ot's untouched result, so a wrong reduction in the gateway shows up as a ✗.

const START = '2026-11-09T16:00:00.000Z';
const END = '2026-11-09T16:30:00.000Z';
const BACKEND_OT = {
  peak: 30,
  series: {
    timeseries: [
      { time: '2026-11-09T15:59:00Z', value: 1 }, // outside the window
      { time: '2026-11-09T16:00:05Z', value: 10 },
      { time: '2026-11-09T16:07:05Z', value: 20.12345 },
      { time: '2026-11-09T16:10:00Z', value: null }, // backend-ot's gap marker
      { time: '2026-11-09T16:15:05Z', value: 30 },
    ],
  },
};

describe('checkAgainstBackendOt', () => {
  it('passes every reading that matches (offsets in whole seconds, values to 3 decimals)', () => {
    const forAi = {
      peak: 30,
      series: {
        resolution: 'every reading',
        timeseries: { start: START, offsets_s: [5, 425, 905], values: [10, 20.123, 30] },
      },
    };
    expect(checkAgainstBackendOt(forAi, BACKEND_OT, START, END)).toEqual([
      { path: 'series', ok: true, summary: '3 of 3 readings match backend-ot', differences: [] },
    ]);
  });

  it('names the readings that differ or are missing', () => {
    const forAi = {
      series: { resolution: 'every reading', timeseries: { start: START, offsets_s: [5, 425], values: [10, 21] } },
    };
    const [check] = checkAgainstBackendOt(forAi, BACKEND_OT, START, END);
    expect([check.ok, check.summary]).toEqual([false, '1 of 3 readings match backend-ot']);
    expect(check.differences).toEqual([
      'row 2: AI 2026-11-09T16:07:05.000Z = 21, backend-ot 2026-11-09T16:07:05Z = 20.12345',
      'row 3: AI nothing, backend-ot 2026-11-09T16:15:05Z = 30',
    ]);
  });

  it("passes rows that are backend-ot's first reading of each interval", () => {
    const forAi = {
      series: {
        resolution: 'first reading every 15 min',
        timeseries: [{ time: '2026-11-09T16:00:05Z', value: 10 }, { time: '2026-11-09T16:15:05Z', value: 30 }],
      },
    };
    const [check] = checkAgainstBackendOt(forAi, BACKEND_OT, START, END);
    expect([check.ok, check.summary]).toEqual([true, "2 of 2 rows are backend-ot's first reading of each 15 min (from 3 readings)"]);
  });

  it('fails a row that is not the first reading of its interval', () => {
    const forAi = {
      series: {
        resolution: 'first reading every 15 min',
        timeseries: [{ time: '2026-11-09T16:07:05Z', value: 20.12345 }, { time: '2026-11-09T16:15:05Z', value: 30 }],
      },
    };
    const [check] = checkAgainstBackendOt(forAi, BACKEND_OT, START, END);
    expect(check.ok).toBe(false);
    expect(check.differences).toEqual(['row 1: AI 2026-11-09T16:07:05Z = 20.12345, backend-ot 2026-11-09T16:00:05Z = 10']);
  });

  it('checks each series of a list, and nothing for a scalar result', () => {
    const forAi = { series: [{ resolution: 'every reading', timeseries: { start: START, offsets_s: [], values: [] } }] };
    const original = { series: [{ timeseries: [] }] };
    expect(checkAgainstBackendOt(forAi, original, START, END).map(check => [check.path, check.ok])).toEqual([['series[0]', true]]);
    expect(checkAgainstBackendOt({ efficiency_pct: 88 }, { efficiency_pct: 88 }, START, END)).toEqual([]);
  });
});
