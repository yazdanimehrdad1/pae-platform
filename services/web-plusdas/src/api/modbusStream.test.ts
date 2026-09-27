import { describe, expect, it, vi } from 'vitest';
import type { ModbusRegisterSnapshot } from '@/api/types/modbusStream';
import { modbusStreamApi } from './modbusStream';

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('modbusStreamApi.getSnapshot', () => {
  it('GETs the snapshot of one session by id', async () => {
    const snapshot: ModbusRegisterSnapshot = {
      timestamps: ['2026-09-27T06:30:14Z', '2026-09-27T06:30:13Z'],
      registers: [{ address: 1, values: [4, 1], label: 'dc_bus_voltage', data_type: 'uint16' }],
    };
    const fetchMock = stubFetch(200, snapshot);

    await expect(modbusStreamApi.getSnapshot('abc-123')).resolves.toEqual(snapshot);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/modbus-live-stream-register-snapshot/registers?session_id=abc-123');
    expect(init?.method ?? 'GET').toBe('GET');
  });

  it('rejects with the backend detail when the session expired', async () => {
    stubFetch(404, { detail: 'Session not found or expired' });

    await expect(modbusStreamApi.getSnapshot('gone')).rejects.toMatchObject({
      detail: 'Session not found or expired',
    });
  });
});
