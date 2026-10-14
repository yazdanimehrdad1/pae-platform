import { describe, expect, it } from 'vitest';
import type { ReportRunStatus } from '@/api/types/reports';
import { formatReportTime, formatValue, isPending, windowLabel } from '@/features/reports/lib/format';

describe('formatReportTime', () => {
  it("shows the instant in the site's zone", () => {
    expect(formatReportTime('2026-10-13T07:00:00Z', 'America/Los_Angeles')).toBe('13 Oct 2026, 00:00');
    expect(formatReportTime('2026-10-13T07:00:00Z', 'UTC')).toBe('13 Oct 2026, 07:00');
  });
});

describe('formatValue', () => {
  it('uses fewer decimals for bigger numbers, and a dash for nothing', () => {
    expect(formatValue(1234.567, 'kW')).toBe('1,235 kW');
    expect(formatValue(12.3456)).toBe('12.35');
    expect(formatValue(0.12345, '%')).toBe('0.123 %');
    expect(formatValue(null, 'kW')).toBe('—');
    expect(formatValue(undefined)).toBe('—');
  });
});

describe('windowLabel', () => {
  it('names each kind of window', () => {
    expect(windowLabel({ kind: 'rolling', duration: '1W' })).toBe('Last 7 days');
    expect(windowLabel({ kind: 'calendar', period: 'day', offset: -1 })).toBe('Yesterday');
    expect(windowLabel({ kind: 'calendar', period: 'month', offset: 0 })).toBe('This month so far');
    expect(windowLabel({ kind: 'calendar', period: 'week', offset: -3 })).toBe('3 weeks ago');
    expect(windowLabel({ kind: 'fixed', start_time: '2026-10-01T00:00:00Z', end_time: '2026-10-02T00:00:00Z' })).toBe('Fixed range');
  });
});

describe('isPending', () => {
  it('is true until the worker has finished', () => {
    const statuses: ReportRunStatus[] = ['queued', 'running', 'succeeded', 'failed'];
    expect(statuses.map(isPending)).toEqual([true, true, false, false]);
  });
});
