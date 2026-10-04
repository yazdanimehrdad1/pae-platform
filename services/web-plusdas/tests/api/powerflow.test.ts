import { afterEach, describe, expect, it, vi } from 'vitest';
import { powerflowApi } from '@/api/powerflow';

function stubFetch(status: number, body: unknown, contentType = 'application/json') {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  // A fresh Response per call: a body can only be read once.
  const fetchMock = vi.fn().mockImplementation(async () => new Response(text, { status, headers: { 'Content-Type': contentType } }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe('powerflowApi', () => {
  it('calls the simulator same-origin under /powerflow-api', async () => {
    const fetchMock = stubFetch(200, { active: 'a', sites: ['a', 'b'] });
    await expect(powerflowApi.listSites()).resolves.toEqual({ active: 'a', sites: ['a', 'b'] });
    expect(fetchMock.mock.calls[0][0]).toBe('/powerflow-api/sites');
  });

  it('activates a site with POST and an encoded name', async () => {
    const fetchMock = stubFetch(200, {});
    await powerflowApi.activateSite('my site');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/powerflow-api/sites/my%20site/activate');
    expect(init.method).toBe('POST');
  });

  it('sends a BESS setpoint as a JSON PUT', async () => {
    const fetchMock = stubFetch(200, { clamped: false, flags: [], accepted: {}, requested: {}, asset_id: 'bess1', asset_type: 'bess' });
    await powerflowApi.setBess('bess1', { p_kw: 1500, mode: 'pq' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/powerflow-api/assets/bess/bess1/setpoint');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).toEqual({ p_kw: 1500, mode: 'pq' });
  });

  it('passes restore overwrite and step count as query parameters', async () => {
    const fetchMock = stubFetch(200, {});
    await powerflowApi.restoreDefaults(true);
    await powerflowApi.step(5);
    expect(fetchMock.mock.calls[0][0]).toBe('/powerflow-api/defaults/restore?overwrite=true');
    expect(fetchMock.mock.calls[1][0]).toBe('/powerflow-api/sim/step?count=5');
  });

  it('returns a profile CSV as text', async () => {
    stubFetch(200, 'timestamp,p_kw\n2026-06-21T00:00:00Z,500\n', 'text/csv');
    await expect(powerflowApi.getProfileCsv('load', 'typical')).resolves.toContain('timestamp,p_kw');
  });

  it('throws the error body (409 with a detail)', async () => {
    stubFetch(409, { detail: 'stop the simulation first' });
    await expect(powerflowApi.activateSite('a')).rejects.toEqual({ detail: 'stop the simulation first' });
  });
});
