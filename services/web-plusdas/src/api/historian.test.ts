import { afterEach, describe, expect, it, vi } from 'vitest';
import { historianApi } from './historian';

function stubFetch(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe('historianApi.getRecentReadings', () => {
  it("asks for every point's newest N readings, with no time window and no point ids", async () => {
    const fetchMock = stubFetch({ meta: {}, readings: {} });
    await historianApi.getRecentReadings('1001', '2', 10);
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/device-point-readings/timeseries/site/1001/device/2?limit=10');
  });
});
