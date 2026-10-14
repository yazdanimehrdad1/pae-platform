import { describe, expect, it } from 'vitest';
import type { AlarmEventsTableResult, PointStatsTableResult } from '@/api/types/reports';
import { alarmEventsCsv, fileName, pointStatsCsv, toCsv } from '@/features/reports/lib/csv';

describe('toCsv', () => {
  it('quotes cells with commas, quotes or line breaks, and leaves the rest', () => {
    expect(toCsv([['a', 'b,c', 'say "hi"', 'two\nlines', null, 3]])).toBe('a,"b,c","say ""hi""","two\nlines",,3');
    expect(toCsv([['x'], ['y']])).toBe('x\r\ny');
  });
});

describe('fileName', () => {
  it('keeps lower-case words only', () => {
    expect(fileName('Daily Energy (Site 1)', 'hourly_stats')).toBe('daily-energy-site-1-hourly_stats');
  });
});

describe('pointStatsCsv', () => {
  const block: PointStatsTableResult = {
    kind: 'point_stats_table', block_id: 'hourly', stats: ['max', 'count'], bucket: 'hour',
    rows: [{
      point_id: 1, point_name: 'active_power', device_id: 2, device_name: 'meter', unit: 'kW',
      bucket_start: '2026-10-13T07:00:00Z', values: { max: 12.3456, count: 6 },
    }],
  };

  it('has a bucket column in site time and keeps raw values', () => {
    expect(pointStatsCsv(block, 'America/Los_Angeles').split('\r\n')).toEqual([
      'Point,Device,Hour (America/Los_Angeles),Unit,Max,Samples',
      'active_power,meter,"13 Oct 2026, 00:00",kW,12.3456,6',
    ]);
  });

  it('has no bucket column for a whole-window table', () => {
    expect(pointStatsCsv({ ...block, bucket: 'none' }, 'UTC').split('\r\n')[0]).toBe('Point,Device,Unit,Max,Samples');
  });
});

describe('alarmEventsCsv', () => {
  it('lists every event with times in site time', () => {
    const block: AlarmEventsTableResult = {
      kind: 'alarm_events_table', block_id: 'alarms', total_count: 1,
      rows: [{
        event_id: 1, alarm_name: 'trip', severity: 'fault', device_name: null, raised_at: '2026-10-13T07:00:00Z',
        cleared_at: null, duration_seconds: 60, value_at_raise: null, message: 'tripped, again',
      }],
    };
    expect(alarmEventsCsv(block, 'UTC').split('\r\n')[1]).toBe('trip,fault,,"13 Oct 2026, 07:00",,60,,"tripped, again"');
  });
});
