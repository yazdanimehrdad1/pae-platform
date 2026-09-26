import { describe, expect, it, vi } from 'vitest';
import type { SiteRecord } from '@/shared/types/site';
import { sitesApi } from './sites';

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
      capacity: '5 MW',
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
