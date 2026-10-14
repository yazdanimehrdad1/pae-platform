import { describe, expect, it } from 'vitest';
import { defaultCadence, describeCadence, describeRetention } from '@/features/reports/lib/cadence';

describe('describeCadence', () => {
  it('says each cadence in words', () => {
    expect(describeCadence({ kind: 'hourly', minute: 5 })).toBe('Every hour at :05');
    expect(describeCadence({ kind: 'daily', time: '06:00' })).toBe('Every day at 06:00');
    expect(describeCadence({ kind: 'weekly', time: '07:30', weekdays: [4, 0] })).toBe('Every Monday and Friday at 07:30');
    expect(describeCadence({ kind: 'weekly', time: '07:30', weekdays: [0, 2, 4] })).toBe('Every Monday, Wednesday and Friday at 07:30');
    expect(describeCadence({ kind: 'weekly', time: '08:00', weekdays: [0, 1, 2, 3, 4] })).toBe('Every weekday at 08:00');
    expect(describeCadence({ kind: 'weekly', time: '08:00', weekdays: [0, 1, 2, 3, 4, 5, 6] })).toBe('Every day at 08:00');
    expect(describeCadence({ kind: 'monthly', time: '05:00', day_of_month: 1 })).toBe('On day 1 of every month at 05:00');
  });
});

describe('describeRetention', () => {
  it('names what is kept', () => {
    expect(describeRetention(7, null)).toBe('Keeps the last 7 reports');
    expect(describeRetention(1, null)).toBe('Keeps the last 1 report');
    expect(describeRetention(null, 30)).toBe('Keeps 30 days');
    expect(describeRetention(7, 30)).toBe('Keeps the last 7 reports, at most 30 days old');
    expect(describeRetention(null, null)).toBe('Keeps every report');
  });
});

describe('defaultCadence', () => {
  it('starts each kind at a sensible time', () => {
    expect(defaultCadence('weekly')).toEqual({ kind: 'weekly', time: '06:00', weekdays: [0] });
    expect(defaultCadence('monthly')).toEqual({ kind: 'monthly', time: '06:00', day_of_month: 1 });
  });
});
