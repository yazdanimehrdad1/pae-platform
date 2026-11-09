import { describe, expect, it } from 'vitest';
import type { ProfileDevice, SiteFunction } from '@/api/types/siteProfiles';
import { appliesTo, devicesFor } from '@/features/site-profiles/lib/functions';

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
