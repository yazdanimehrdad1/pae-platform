import { describe, expect, it } from 'vitest';
import type { DevicePoint } from '@/api/types/devicePoints';
import type { CatalogPoint } from '../hooks/usePointCatalog';
import { describeDiscreteSeries, stateLabel } from './discreteSeries';

const catalog = new Map<string, CatalogPoint>([
  ['1', { deviceId: '9', point: { id: 1, name: 'inverter_state', data_type: 'enum16', enum_detail: { '2': 'running', '1': 'off' } } as unknown as DevicePoint }],
  ['2', { deviceId: '9', point: { id: 2, name: 'fault_flags', data_type: 'bitfield16', bitfield_detail: { '0': 'trip' } } as unknown as DevicePoint }],
  ['3', { deviceId: '9', point: { id: 3, name: 'voltage', data_type: 'float32' } as unknown as DevicePoint }],
]);
const display = { name: 'series', color: '#000' };

describe('describeDiscreteSeries', () => {
  it('lists enum states in value order, adding unlabelled values seen in the data', () => {
    const series = describeDiscreteSeries('1', catalog, [{ timestamp: 1, '1': 5 }, { timestamp: 2, '1': 2 }], display);
    expect(series?.kind).toBe('enum');
    expect(series?.states).toEqual([
      { value: 1, label: 'off' }, { value: 2, label: 'running' }, { value: 5, label: 'Unknown (5)' },
    ]);
    expect(stateLabel(series!, 2)).toBe('running');
  });

  it('describes a bit as off/on', () => {
    expect(describeDiscreteSeries('2:bit0', catalog, [], display)).toMatchObject({ kind: 'bit', states: [{ value: 0 }, { value: 1 }] });
  });

  it('returns null for analog points and unknown ids', () => {
    expect(describeDiscreteSeries('3', catalog, [], display)).toBeNull();
    expect(describeDiscreteSeries('99', catalog, [], display)).toBeNull();
  });
});
