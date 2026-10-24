import { describe, expect, it } from 'vitest';
import { latestReadingTime } from '@/features/historian/lib/latestReading';

describe('latestReadingTime', () => {
  it('is the newest reading across the points', () => {
    const lines = {
      '7': [{ timestamp: 1000, '7': 1 }, { timestamp: 3000, '7': 2 }],
      '9': [{ timestamp: 2000, '9': 5 }],
    };
    expect(latestReadingTime(lines, ['7', '9'])).toBe(3000);
  });

  it('skips gap markers', () => {
    expect(latestReadingTime({ '7': [{ timestamp: 1000, '7': 1 }, { timestamp: 5000, '7': null }] }, ['7'])).toBe(1000);
  });

  it('leaves out forecasts (they reach into the future) and profile functions', () => {
    const lines = {
      '7': [{ timestamp: 1000, '7': 1 }],
      'fc:site:pv_power': [{ timestamp: 9000, 'fc:site:pv_power': 3 }],
      'fn:load-profile': [{ timestamp: 8000, 'fn:load-profile': 4 }],
    };
    expect(latestReadingTime(lines, Object.keys(lines))).toBe(1000);
  });

  it('is null without readings', () => {
    expect(latestReadingTime({ '7': [] }, ['7'])).toBeNull();
    expect(latestReadingTime({}, [])).toBeNull();
  });
});
