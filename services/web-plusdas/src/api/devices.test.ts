import { describe, expect, it, vi } from 'vitest';
import type { DeviceRecord } from '@/shared/types/device';
import { devicesApi } from './devices';

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const pvDevice: DeviceRecord = {
  device_id: 1,
  site_id: 1001,
  name: 'mock-device-1',
  type: 'PV',
  protocol: 'Modbus',
  vendor: 'SEL',
  model: 'RTAC',
  host: 'mock-modbus',
  port: 502,
  server_address: 1,
  poll_enabled: true,
  read_from_aggregator: true,
  modbus_address_mode: 'one_based',
  scan_ranges: { holding: [{ start_index: 0, count: 10 }], input: [], coils: [] },
  scan_ranges_locked: false,
  description: null,
  created_at: '2026-09-24T00:00:00Z',
  updated_at: '2026-09-25T00:00:00Z',
  points: {
    standardized: [],
    native: [{
      id: 4, name: 'voltage', category: 'NATIVE', address: 1, size: 1, data_type: 'uint16',
      byte_order: 'big', word_order: 'msw_first', device_id: 1, site_id: 1001,
    }],
    virtual: [],
  },
};

describe('devicesApi.deletePoints', () => {
  it('repeats point_ids, the integer-array form the contract declares', async () => {
    // backend-ot rejects a comma-joined point_ids=4,5 with 422 (int_parsing).
    const fetchMock = stubFetch(200, []);

    await devicesApi.deletePoints('1001', 1, [4, 5], { mode: 'soft' });

    const url = new URL(fetchMock.mock.calls[0][0], 'http://web.test');
    expect(url.pathname).toBe('/api/device-points/site/1001/device/1');
    expect(url.searchParams.getAll('point_ids')).toEqual(['4', '5']);
    expect(url.searchParams.get('mode')).toBe('soft');
    expect(url.searchParams.get('confirm')).toBe('false');
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
  });
});

describe('devicesApi.getBySite', () => {
  it('maps devices to the UI model', async () => {
    stubFetch(200, [pvDevice]);

    const [device] = await devicesApi.getBySite('1001');

    expect(device).toMatchObject({
      id: '1',
      name: 'mock-device-1',
      type: 'pv',
      points: ['voltage'],
      make: 'SEL',
      commStatus: 'connected',
    });
    expect(device.modbusConfig?.scanRanges?.holding).toEqual([{ startIndex: 0, count: 10 }]);
  });

  it('treats backend-ot\'s "no devices found" 404 as an empty site', async () => {
    stubFetch(404, { detail: 'No devices found for site 1001' });

    await expect(devicesApi.getBySite('1001')).resolves.toEqual([]);
  });

  it('rethrows any other error', async () => {
    stubFetch(500, { detail: 'database unavailable' });

    await expect(devicesApi.getBySite('1001')).rejects.toEqual({ detail: 'database unavailable' });
  });
});
