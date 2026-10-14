import { describe, expect, it } from 'vitest';
import { isTimeZone, timeZoneGroups, utcOffset } from '@/features/sites/lib/timeZones';

const SUMMER = new Date('2026-07-01T12:00:00Z');
const WINTER = new Date('2026-01-15T12:00:00Z');

describe('utcOffset', () => {
  it('is the offset at that moment, so it follows DST', () => {
    expect(utcOffset('America/Los_Angeles', SUMMER)).toBe('UTC−07:00');
    expect(utcOffset('America/Los_Angeles', WINTER)).toBe('UTC−08:00');
    expect(utcOffset('Asia/Kolkata', WINTER)).toBe('UTC+05:30');
    expect(utcOffset('UTC', WINTER)).toBe('UTC+00:00');
  });
});

describe('isTimeZone', () => {
  it('accepts IANA zones only', () => {
    expect(isTimeZone('Europe/Berlin')).toBe(true);
    expect(isTimeZone('Mars/Olympus')).toBe(false);
  });
});

describe('timeZoneGroups', () => {
  const groups = timeZoneGroups([], WINTER);
  const zones = groups.flatMap(group => group.zones.map(option => option.zone));

  it('starts with UTC, then regions A to Z', () => {
    expect(groups[0]).toEqual({ region: 'UTC', zones: [{ zone: 'UTC', city: 'UTC', offset: 'UTC+00:00' }] });
    const regions = groups.slice(1).map(group => group.region);
    expect(regions).toEqual([...regions].sort((first, second) => first.localeCompare(second)));
  });

  it('lists the zones people pick, once each, with a readable city', () => {
    expect(zones).toEqual(expect.arrayContaining(['America/Los_Angeles', 'America/New_York', 'Europe/Berlin', 'Asia/Tokyo']));
    expect(new Set(zones).size).toBe(zones.length);
    const losAngeles = groups.find(group => group.region === 'America')!.zones.find(option => option.zone === 'America/Los_Angeles');
    expect(losAngeles).toEqual({ zone: 'America/Los_Angeles', city: 'Los Angeles', offset: 'UTC−08:00' });
  });

  it("includes a site's stored zone even if the browser doesn't list it, but never an invalid one", () => {
    const withExtra = timeZoneGroups(['US/Pacific', 'Mars/Olympus'], WINTER).flatMap(group => group.zones.map(option => option.zone));
    expect(withExtra).toContain('US/Pacific');
    expect(withExtra).not.toContain('Mars/Olympus');
  });
});
