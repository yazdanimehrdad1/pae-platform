import { afterEach, describe, expect, it, vi } from 'vitest';
import { siteFunctionsApi } from '@/api/siteFunctions';

function stubFetch(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const series = (id: number) => ({ id, name: `p${id}`, data_type: 'float32', timeseries: [] });

afterEach(() => vi.unstubAllGlobals());

describe('siteFunctionsApi.list', () => {
  it("asks for the site's declared functions", async () => {
    const fetchMock = stubFetch({ site_id: 1001, profile: 'alpha_solar', endpoints: [] });
    await siteFunctionsApi.list('1001');
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/site-functions/site/1001');
  });
});

describe('siteFunctionsApi.getSeries', () => {
  it('calls a site function with a preset window and wraps a single series in a list', async () => {
    const fetchMock = stubFetch({ site_id: 1001, peak_kw: 3, series: series(5) });
    const result = await siteFunctionsApi.getSeries({ siteId: '1001', name: 'site-poi-power', timeRange: '1H', maxPoints: 2000 });
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/site-functions/site/1001/site-poi-power?max_points=2000&time_range=1H');
    expect(result).toEqual([series(5)]);
  });

  it('calls a device function with a custom window and keeps a list of series', async () => {
    const fetchMock = stubFetch({ series: [series(1), series(2)] });
    const result = await siteFunctionsApi.getSeries({
      siteId: '1001', name: 'device-trend', deviceId: '7', startTime: '2026-10-01T00:00:00Z', endTime: '2026-10-02T00:00:00Z',
    });
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      '/api/site-functions/site/1001/device/7/device-trend?start_time=2026-10-01T00%3A00%3A00Z&end_time=2026-10-02T00%3A00%3A00Z',
    );
    expect(result.map(entry => entry.id)).toEqual([1, 2]);
  });
});
