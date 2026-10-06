import { describe, expect, it } from 'vitest';
import type { DeviceHistory, PointReading } from '@/api/types/powerflow';
import {
  deviceName,
  filterPoints,
  formatReading,
  isTrendable,
  registersByPoint,
  trendRows,
} from '@/features/simulation/lib/measurements';

const reading = (overrides: Partial<PointReading>): PointReading => ({
  point: 'W', label: 'Active Power', unit: 'W', data_type: 'int16', served: 'yes', value: 1_234_567.8, text: null,
  ...overrides,
});

describe('measurements helpers', () => {
  it('names devices', () => {
    expect(deviceName({ kind: 'bess', asset_id: 'bess1' })).toBe('BESS bess1');
    expect(deviceName({ kind: 'poi_meter', asset_id: 'meter' })).toBe('POI meter');
  });

  it('formats numbers, codes and missing values', () => {
    expect(formatReading(reading({}))).toBe(`${(1_234_568).toLocaleString()} W`);
    expect(formatReading(reading({ value: 0.98765, unit: '' }))).toBe('0.9877');
    expect(formatReading(reading({ data_type: 'enum16', value: 3, text: 'RUNNING', unit: '' }))).toBe('RUNNING (3)');
    expect(formatReading(reading({ data_type: 'bitfield16', value: 0, text: '', unit: '' }))).toBe('0 (none)');
    expect(formatReading(reading({ served: 'no', value: null }))).toBe('–');
  });

  it('filters and picks trendable points', () => {
    const points = [
      reading({}),
      reading({ point: 'InvSt', label: 'Inverter State', data_type: 'enum16' }),
      reading({ point: 'TmpCab', label: 'Cabinet Temperature', served: 'no', value: null }),
    ];
    expect(filterPoints(points, '', false).map((point) => point.point)).toEqual(['W', 'InvSt']);
    expect(filterPoints(points, 'temp', true).map((point) => point.point)).toEqual(['TmpCab']);
    expect(points.map(isTrendable)).toEqual([true, false, false]);
  });

  it('builds chart rows with gaps for missing values', () => {
    const history: DeviceHistory = {
      kind: 'bess', asset_id: 'bess1', base: 1000,
      points: [{ point: 'W', label: 'Active Power', unit: 'W' }, { point: 'WSet', label: 'Active Power Setpoint', unit: 'W' }],
      samples: [{ step_id: 1, sim_time: '2026-06-21T12:00:01Z', converged: true, values: [500, null] }],
    };
    expect(trendRows(history)).toEqual([{ t: Date.parse('2026-06-21T12:00:01Z'), step: 1, W: 500, WSet: null }]);
  });

  it('lists each point\'s register addresses by data type width', () => {
    const register = (point: string, address: number, data_type: string) =>
      ({ point, address, data_type, unit: '', scale: 1, powerflow_server: 'yes' as const });
    const addresses = registersByPoint({
      registers: [register('W', 1000, 'int32'), register('Hz', 1002, 'uint16'), register('WH', 1003, 'uint64')],
    });
    expect(addresses.get('W')).toEqual([1000, 1001]);
    expect(addresses.get('Hz')).toEqual([1002]);
    expect(addresses.get('WH')).toEqual([1003, 1004, 1005, 1006]);
    expect(registersByPoint(undefined).size).toBe(0);
  });
});
