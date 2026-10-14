import { describe, expect, it } from 'vitest';
import { fromZonedInput, toZonedInput } from '@/shared/lib/zonedTime';

const PACIFIC = 'America/Los_Angeles';

describe('fromZonedInput', () => {
  it("reads the wall time in the site's zone", () => {
    expect(fromZonedInput('2026-10-13T00:00', PACIFIC)).toBe('2026-10-13T07:00:00.000Z'); // PDT
    expect(fromZonedInput('2026-01-15T00:00', PACIFIC)).toBe('2026-01-15T08:00:00.000Z'); // PST
    expect(fromZonedInput('2026-10-13T00:00', 'UTC')).toBe('2026-10-13T00:00:00.000Z');
  });

  it('handles the days the clocks change', () => {
    expect(fromZonedInput('2026-03-08T03:00', PACIFIC)).toBe('2026-03-08T10:00:00.000Z'); // just after the spring gap
    expect(fromZonedInput('2026-11-01T00:00', PACIFIC)).toBe('2026-11-01T07:00:00.000Z');
    expect(fromZonedInput('2026-11-02T00:00', PACIFIC)).toBe('2026-11-02T08:00:00.000Z');
  });

  it('refuses anything that is not a datetime-local value', () => {
    expect(() => fromZonedInput('2026-10-13', PACIFIC)).toThrow();
  });
});

describe('toZonedInput', () => {
  it("shows the instant on the site's wall clock", () => {
    expect(toZonedInput('2026-10-13T07:00:00Z', PACIFIC)).toBe('2026-10-13T00:00');
    expect(toZonedInput('2026-01-15T08:30:00Z', PACIFIC)).toBe('2026-01-15T00:30');
  });

  it('round-trips with fromZonedInput', () => {
    for (const wall of ['2026-06-30T23:45', '2026-12-31T00:00', '2026-11-01T12:00']) {
      expect(toZonedInput(fromZonedInput(wall, PACIFIC), PACIFIC)).toBe(wall);
    }
  });
});
