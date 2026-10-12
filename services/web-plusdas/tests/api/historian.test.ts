import { afterEach, describe, expect, it, vi } from 'vitest';
import { historianApi } from '@/api/historian';

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

describe('historianApi.getDevicePointReadings', () => {
  it('sends a chart request as max_points, with no limit', async () => {
    const fetchMock = stubFetch({ meta: {}, readings: {} });
    await historianApi.getDevicePointReadings({ siteId: '1002', deviceId: '3', pointIds: ['5', '6'], timeRange: '1W', maxPoints: 2000 });
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      '/api/device-point-readings/timeseries/site/1002/device/3?point_ids=5%2C6&max_points=2000&time_range=1W',
    );
  });

  it('sends no max_points when not asked', async () => {
    const fetchMock = stubFetch({ meta: {}, readings: {} });
    await historianApi.getDevicePointReadings({ siteId: '1002', deviceId: '3', pointIds: ['5'], startTime: 'a', endTime: 'b' });
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/device-point-readings/timeseries/site/1002/device/3?point_ids=5&start_time=a&end_time=b');
  });
});
