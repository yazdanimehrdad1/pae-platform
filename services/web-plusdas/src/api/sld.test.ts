import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SiteSldResponse } from '@/api/types/sld';
import { sldApi } from './sld';

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

  it('throws the FastAPI error body on 404', async () => {
    const detail = { error: 'NotFoundError', message: 'Site 1002 has no single line diagram' };
    stubFetch(404, { detail });
    await expect(sldApi.getBySite(1002)).rejects.toEqual({ detail });
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
