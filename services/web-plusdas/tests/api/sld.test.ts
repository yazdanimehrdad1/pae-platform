import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SiteSldResponse } from '@/api/types/sld';
import { sldApi } from '@/api/sld';

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const stored: SiteSldResponse = {
  site_id: 1001,
  revision: 3,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-02T00:00:00Z',
  sld: {
    schema_version: 1,
    nodes: [{ id: 'utility', type: 'grid', name: 'Utility', col: 0, row: 0 }],
    buses: [],
    connections: [],
  },
};

afterEach(() => vi.unstubAllGlobals());

describe('sldApi.getBySite', () => {
  it('GETs the site SLD same-origin, without a trailing slash', async () => {
    const fetchMock = stubFetch(200, stored);
    await expect(sldApi.getBySite(1001)).resolves.toEqual(stored);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/sites/1001/sld');
  });

  it('is null when the site has no diagram yet', async () => {
    stubFetch(404, { detail: { error: 'SiteSldNotFoundError', message: 'Site 1002 has no single line diagram' } });
    await expect(sldApi.getBySite(1002)).resolves.toBeNull();
  });

  it('throws any other error, e.g. an unknown site, whatever its message says', async () => {
    const detail = { error: 'NotFoundError', message: 'Site 9 has no single line diagram' };
    stubFetch(404, { detail });
    await expect(sldApi.getBySite(9)).rejects.toEqual({ detail });
  });
});

describe('sldApi.getValues', () => {
  it('GETs the live values of the linked elements', async () => {
    const values = { site_id: 1001, sld_revision: 2, generated_at: '2026-10-02T00:00:00Z', nodes: [] };
    const fetchMock = stubFetch(200, values);
    await expect(sldApi.getValues(1001)).resolves.toEqual(values);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/sites/1001/sld/values');
  });
});

describe('sldApi.save', () => {
  it('PUTs the diagram with the revision it replaces', async () => {
    const fetchMock = stubFetch(200, { ...stored, revision: 4 });
    await sldApi.save(1001, stored.sld, 3);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/sites/1001/sld');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).toEqual({ sld: stored.sld, revision: 3 });
  });

  it('sends a null revision to create the first diagram', async () => {
    const fetchMock = stubFetch(200, stored);
    await sldApi.save(1001, stored.sld, null);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).revision).toBeNull();
  });
});
