import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AlarmDefinitionCreateRequest } from '@/api/types/alarms';
import { alarmsApi } from '@/api/alarms';
import { devicesApi } from '@/api/devices';
import { historianApi } from '@/api/historian';

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const call = (fetchMock: ReturnType<typeof vi.fn>) => {
  const [url, init] = fetchMock.mock.calls[0];
  return { url: String(url), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(init.body) : undefined };
};

afterEach(() => vi.unstubAllGlobals());

describe('alarmsApi', () => {
  it('gets the snapshot of a site', async () => {
    const fetchMock = stubFetch(200, { site_id: 1001, now: '2026-09-30T12:00:00Z', definitions: [], events: [], log: [] });
    await alarmsApi.getSnapshot('1001');
    expect(call(fetchMock)).toMatchObject({ url: '/api/alarms/site/1001/snapshot', method: 'GET' });
  });

  it('queries events with a range and only the filters given', async () => {
    const fetchMock = stubFetch(200, []);
    await alarmsApi.queryEvents('1001', { startTime: '2026-09-30T00:00:00.000Z', endTime: '2026-09-30T12:00:00.000Z', severity: 'fault', definitionId: 5 });
    const url = new URL(call(fetchMock).url, 'http://host');
    expect(url.pathname).toBe('/api/alarms/site/1001/events');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      start_time: '2026-09-30T00:00:00.000Z', end_time: '2026-09-30T12:00:00.000Z', severity: 'fault', definition_id: '5',
    });
  });

  it('creates, updates and deletes definitions', async () => {
    const request: AlarmDefinitionCreateRequest = {
      name: 'pv_silent', severity: 'fault', message: '', enabled: true, notify_mobile: false, notify_email: false,
      rule: { kind: 'comms_stale', device_id: 3, stale_after_sec: 60 },
    };
    let fetchMock = stubFetch(201, {});
    await alarmsApi.create('1001', request);
    expect(call(fetchMock)).toEqual({ url: '/api/alarms/site/1001/definitions', method: 'POST', body: request });

    fetchMock = stubFetch(200, {});
    await alarmsApi.update('1001', 7, { enabled: false });
    expect(call(fetchMock)).toEqual({ url: '/api/alarms/site/1001/definitions/7', method: 'PUT', body: { enabled: false } });

    fetchMock = stubFetch(200, {});
    await alarmsApi.remove('1001', 7);
    expect(call(fetchMock)).toMatchObject({ url: '/api/alarms/site/1001/definitions/7', method: 'DELETE' });
  });

  it("surfaces backend-ot's error detail", async () => {
    stubFetch(409, { detail: { error: 'ConflictError', message: 'Site 1001 already has 20 enabled alarms', max_enabled: 20 } });
    await expect(alarmsApi.update('1001', 7, { enabled: true })).rejects.toMatchObject({ detail: { max_enabled: 20 } });
  });
});

describe('readings and device records used by the alarms page', () => {
  it('gets the latest readings of a device', async () => {
    const fetchMock = stubFetch(200, { meta: {}, readings: {} });
    await historianApi.getLatestReadings('1001', '2');
    expect(call(fetchMock).url).toBe('/api/device-point-readings/site/1001/device/2/latest');
  });

  it("gets a site's active device records, empty when it has none", async () => {
    let fetchMock = stubFetch(200, []);
    await devicesApi.getRecords('1001');
    expect(call(fetchMock).url).toBe('/api/devices/site/1001/devices');
    fetchMock = stubFetch(404, { detail: 'No devices found for site 1001' });
    expect(await devicesApi.getRecords('1001')).toEqual([]);
  });
});
