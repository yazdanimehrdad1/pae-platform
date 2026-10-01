import { describe, expect, it } from 'vitest';
import type { DevicePoint } from '@/api/types/devicePoints';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { BackendPointReadings } from '@/api/types/historian';
import { buildReadingsTable, formatReading } from './readingsSnapshot';

const point = (id: number, name: string, extra: Partial<DevicePoint> = {}) =>
  ({ id, name, category: 'NATIVE', data_type: 'uint16', unit: null, ...extra }) as DevicePoint;

const POWER = point(1, 'power', { unit: 'W' });
const MODE = point(2, 'mode', { data_type: 'enum16', enum_detail: { '0': 'off', '1': 'on' } });
const FLAGS = point(3, 'flags', { data_type: 'bitfield16', bitfield_detail: { '0': 'run', '3': 'trip' } });
const READY = point(4, 'ready', { category: 'VIRTUAL' });
const STD_POWER = point(5, 'STD_POWER', { category: 'STANDARDIZED' });

const device: DevicePointsEntry = {
  deviceId: 2, deviceName: 'bess-1',
  groups: { standardized: [STD_POWER], virtual: [READY], native: [FLAGS, MODE, POWER] },
  points: [STD_POWER, READY, FLAGS, MODE, POWER],
};

const at = (second: number, millis = 0) => new Date(Date.UTC(2026, 9, 1, 12, 0, second, millis)).toISOString();
const series = (pointId: number, samples: [string, number | null][]) => ({
  [String(pointId)]: { id: pointId, name: '', data_type: 'uint16', count: samples.length,
    timeseries: samples.map(([time, value]) => ({ time, value })) },
});
const readings = (...entries: ReturnType<typeof series>[]): BackendPointReadings =>
  ({ meta: {}, readings: Object.assign({}, ...entries) }) as BackendPointReadings;

describe('buildReadingsTable', () => {
  it('lines readings of one poll up in a column, newest first, keyed to the second', () => {
    const table = buildReadingsTable(device, readings(
      series(1, [[at(20, 3), 30], [at(10, 2), 20], [at(0, 1), 10]]),
      series(4, [[at(20, 900), 1], [at(10), 0]]), // computed a little later in the same second
    ));
    expect(table.columns.map(column => column.time)).toEqual([at(20, 900), at(10, 2), at(0, 1)]);
    const rows = Object.fromEntries(table.groups.flatMap(group => group.rows).map(row => [row.point.name, row.cells]));
    expect(rows.power).toEqual([30, 20, 10]);
    expect(rows.ready).toEqual([1, 0, null]);
  });

  it('keeps only the newest N times', () => {
    const samples: [string, number][] = Array.from({ length: 12 }, (_, index) => [at(59 - index), index]);
    const table = buildReadingsTable(device, readings(series(1, samples)), 10);
    expect(table.columns).toHaveLength(10);
    expect(table.columns[0].time).toBe(at(59));
    expect(table.columns.at(-1)!.time).toBe(at(50));
  });

  it('lists every point, grouped standardized, virtual, native, even with no readings', () => {
    const table = buildReadingsTable(device, readings(series(1, [[at(0), 5], [at(1), null]])));
    expect(table.groups.map(group => [group.group, group.rows.map(row => row.point.name)])).toEqual([
      ['standardized', ['STD_POWER']], ['virtual', ['ready']], ['native', ['flags', 'mode', 'power']],
    ]);
    expect(table.groups[0].rows[0].cells).toEqual([null]); // a null value doesn't make a column
  });

  it('is empty of columns when nothing was read', () => {
    expect(buildReadingsTable(device, readings()).columns).toEqual([]);
  });
});

describe('formatReading', () => {
  it('shows enum labels, bitfields in hex with their set bits, and plain numbers', () => {
    expect(formatReading(MODE, 1)).toEqual({ text: 'on', title: '1' });
    expect(formatReading(FLAGS, 9)).toEqual({ text: '0x9', title: '0: run, 3: trip' });
    expect(formatReading(FLAGS, 2)).toEqual({ text: '0x2', title: 'no labelled bit set' });
    expect(formatReading(POWER, 1234.5)).toEqual({ text: '1234.5' });
    expect(formatReading(POWER, null)).toEqual({ text: '—' });
  });
});
