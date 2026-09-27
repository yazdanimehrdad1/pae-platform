import { describe, expect, it } from 'vitest';
import type { DiscreteSeries } from '../../lib/discreteSeries';
import { buildStepLayout } from './stepSeries';

const enumSeries: DiscreteSeries = {
  key: '1', kind: 'enum', name: 'state', color: '#000',
  states: [{ value: 1, label: 'off' }, { value: 2, label: 'running' }],
};
const bitSeries: DiscreteSeries = {
  key: '2:bit0', kind: 'bit', name: 'trip', color: '#000',
  states: [{ value: 0, label: 'off' }, { value: 1, label: 'on' }],
};

describe('buildStepLayout', () => {
  it('stacks each series in its own band and maps plotted values back to state labels', () => {
    const layout = buildStepLayout([enumSeries, bitSeries]);
    const [row] = layout.addPlotValues([{ timestamp: 0, '1': 2, '2:bit0': 1 }]);

    expect(row['step:1']).toBe(1);
    expect(row['step:2:bit0']).toBe(3.5);
    expect(layout.tooltipLabel('step:1', 1)).toBe('running');
    expect(layout.tooltipLabel('step:2:bit0', 3.5)).toBe('on');
    expect(layout.tooltipLabel('4', 230)).toBeUndefined();
    expect(layout.selectionKey('step:2:bit0')).toBe('2:bit0');
    expect(layout.selectionKey('4')).toBeUndefined();
  });
});
