import { describe, expect, it } from 'vitest';
import { formatSiteTime, timeZoneAbbreviation } from '@/shared/lib/siteTime';

// Times are written with the zone's usual abbreviation (PST / PDT / MST), the same on every page
// that uses formatSiteTime (System alarms, AI Site Profiles).

describe('formatSiteTime', () => {
  it('writes the zone as PST in winter and PDT in summer for Los Angeles', () => {
    expect(formatSiteTime('2026-11-09T22:21:06Z', 'America/Los_Angeles', { withDate: true })).toBe('09 Nov, 14:21 PST');
    expect(formatSiteTime('2026-07-01T22:21:06Z', 'America/Los_Angeles', { withDate: true })).toBe('01 Jul, 15:21 PDT');
    expect(formatSiteTime('2026-11-09T22:21:06Z', 'America/Los_Angeles')).toBe('14:21:06 PST');
  });

  it('uses the site zone, not the browser: Phoenix is MST all year', () => {
    expect(formatSiteTime('2026-07-01T22:21:06Z', 'America/Phoenix', { withDate: true })).toBe('01 Jul, 15:21 MST');
  });

  it('keeps the offset for a zone without a common abbreviation', () => {
    expect(timeZoneAbbreviation(new Date('2026-11-09T12:00:00Z'), 'Europe/Berlin')).toBe('GMT+1');
  });
});
