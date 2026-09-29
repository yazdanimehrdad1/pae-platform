import { describe, expect, it, vi } from 'vitest';
import type { DeviceRecord } from '@/api/types/devices';
import type { VirtualPointCreateRequest } from '@/api/types/devicePoints';
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

describe('devicesApi.getBySiteWithPoints', () => {
  const point = (id: number, name: string, category: string) => ({
    ...pvDevice.points.native[0], id, name, category,
  });

  it('groups points by category, sorts each group by name, and flattens standardized → virtual → native', async () => {
    stubFetch(200, [{
      ...pvDevice,
      points: {
        standardized: [point(1, 'PV_POWER', 'STANDARDIZED'), point(2, 'pv_energy', 'STANDARDIZED')],
        native: [point(3, 'reg_10', 'NATIVE'), point(4, 'reg_2', 'NATIVE'), point(5, 'Reg_1', 'NATIVE')],
        virtual: [point(6, 'calc_power', 'VIRTUAL')],
      },
    }]);

    const [entry] = await devicesApi.getBySiteWithPoints('1001');

    expect(entry.groups.standardized.map(p => p.name)).toEqual(['pv_energy', 'PV_POWER']);
    expect(entry.groups.native.map(p => p.name)).toEqual(['Reg_1', 'reg_2', 'reg_10']);
    expect(entry.points.map(p => p.id)).toEqual([2, 1, 6, 5, 4, 3]);
  });
});

describe('devicesApi virtual points', () => {
  const request: VirtualPointCreateRequest = {
    name: 'SITE_POWER',
    definition: { kind: 'calculation', function: 'sum', inputs: [4, 5], scale: 1, offset: 0 },
  };

  it('creates through POST .../virtual with the definition in the body', async () => {
    const fetchMock = stubFetch(201, { ...pvDevice.points.native[0], id: 9, name: 'SITE_POWER', category: 'VIRTUAL' });

    const point = await devicesApi.createVirtualPoint('1001', 1, request);

    expect(new URL(fetchMock.mock.calls[0][0], 'http://web.test').pathname).toBe('/api/device-points/site/1001/device/1/virtual');
    expect(fetchMock.mock.calls[0][1].method).toBe('POST');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(request);
    expect(point.category).toBe('VIRTUAL');
  });

  it('updates through PUT .../virtual/{point_id}', async () => {
    const fetchMock = stubFetch(200, { ...pvDevice.points.native[0], id: 9 });

    await devicesApi.updateVirtualPoint('1001', 1, 9, { unit: null });

    expect(new URL(fetchMock.mock.calls[0][0], 'http://web.test').pathname).toBe('/api/device-points/site/1001/device/1/virtual/9');
    expect(fetchMock.mock.calls[0][1].method).toBe('PUT');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ unit: null });
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
