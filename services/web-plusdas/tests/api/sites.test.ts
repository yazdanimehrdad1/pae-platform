import { describe, expect, it, vi } from 'vitest';
import type { SiteHealth, SiteRecord } from '@/api/types/sites';
import { sitesApi } from '@/api/sites';

const alpha: SiteRecord = {
  site_id: 1001,
  client_id: 'alpha-corp',
  name: 'Alpha Solar Farm',
  location: { street: '100 Solar Way', city: 'San Diego', state: 'CA', zip_code: 92101 },
  operator: 'Alpha Ops',
  capacity: '5 MW',
  device_count: 3,
  description: null,
  profile: 'alpha_solar',
  created_at: '2026-09-24T00:00:00Z',
  updated_at: '2026-09-25T00:00:00Z',
  last_update: '2026-09-25T00:00:00Z',
};

function stubSites(body: unknown) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  ));
}

describe('sitesApi.getAll', () => {
  it('maps sites to the UI model', async () => {
    stubSites([alpha]);

    const [site] = await sitesApi.getAll();

    expect(site).toEqual({
      id: '1001',
      name: 'Alpha Solar Farm',
      location: 'San Diego, CA',
      type: 'facility',
      status: 'online',
      deviceCount: 3,
      lastUpdate: '2026-09-25T00:00:00Z',
      operator: 'Alpha Ops',
      description: '',
    });
  });

  it('handles a site without a location (optional in the contract)', async () => {
    stubSites([{ ...alpha, location: null }]);

    const [site] = await sitesApi.getAll();

    expect(site.location).toBe('');
  });
});

describe('sitesApi.getHealth', () => {
  const health: SiteHealth = {
    site_id: 1001,
    generated_at: '2026-10-09T12:00:00Z',
    highest_severity: 'HIGH',
    high_count: 1,
    medium_count: 0,
    low_count: 0,
    unknown_count: 0,
    devices: [],
  };

  it('fetches the site health without a query when unfiltered', async () => {
    stubSites(health);

    const result = await sitesApi.getHealth('1001');

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe('/api/sites/1001/health');
    expect(result).toEqual(health);
  });

  it('repeats the severity and device_ids params', async () => {
    stubSites(health);

    await sitesApi.getHealth('1001', { severity: ['HIGH', 'LOW'], deviceIds: [3, 7] });

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe('/api/sites/1001/health?severity=HIGH&severity=LOW&device_ids=3&device_ids=7');
  });
});
