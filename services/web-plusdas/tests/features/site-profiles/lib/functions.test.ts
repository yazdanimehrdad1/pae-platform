import { describe, expect, it } from 'vitest';
import type { ProfileDevice, SiteFunction } from '@/api/types/siteProfiles';
import { appliesTo, devicesFor, withDisplayTimes } from '@/features/site-profiles/lib/functions';

const DEVICES: ProfileDevice[] = [
  { device_id: 1, name: 'bess1', type: 'BESS' },
  { device_id: 2, name: 'pv1', type: 'INVERTER' },
];
const fn = (kind: SiteFunction['kind'], device_types: string[] = []): SiteFunction =>
  ({ name: `${kind}-x`, kind, summary: 'x', output: 'scalar', device_types, parameters: [] });

describe('devicesFor', () => {
  it('offers no device for a site-wide function', () => {
    expect(devicesFor(fn('site'), DEVICES)).toEqual([]);
  });

  it('offers only the devices of the types a device function applies to', () => {
    expect(devicesFor(fn('device', ['INVERTER']), DEVICES).map(d => d.name)).toEqual(['pv1']);
  });

  it('offers every approved device when the function names no type', () => {
    expect(devicesFor(fn('device'), DEVICES).map(d => d.name)).toEqual(['bess1', 'pv1']);
  });
});

describe('appliesTo', () => {
  it('names the device types a function runs for', () => {
    expect([appliesTo(fn('site')), appliesTo(fn('device', ['BESS', 'ES'])), appliesTo(fn('device'))])
      .toEqual(['Whole site', 'Each BESS / ES', 'Each device']);
  });
});

describe('withDisplayTimes', () => {
  it('shows every UTC timestamp in the given zone and leaves everything else alone', () => {
    const shown = withDisplayTimes({
      start_time: '2026-11-08T22:21:06.211000Z',
      series: { timeseries: { first: { timestamp: '2026-11-09T05:34:14Z', value: 4872 } } },
      unit: 'kW', note: '2026-11-09 is not a timestamp', samples: [{ timestamp: '2026-11-09T22:22:11+00:00' }],
    }, 'America/Los_Angeles') as Record<string, unknown>;
    expect(shown.start_time).toMatch(/^08 Nov, 14:21 /);
    expect(JSON.stringify(shown.series)).toContain('08 Nov, 21:34');
    expect(shown.unit).toBe('kW');
    expect(shown.note).toBe('2026-11-09 is not a timestamp');
    expect(JSON.stringify(shown.samples)).toContain('09 Nov, 14:22');
  });
});
