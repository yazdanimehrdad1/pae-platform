import { describe, expect, it } from 'vitest';
import { assignAxes, axisWidth, groupByAxis, isAxisScale, UNIT_AXIS_COLORS, valueRange, type AxisLine } from '@/features/historian/lib/axes';

const line = (key: string, unit: string | null, color = `#${key}`): AxisLine => ({ key, unit, label: `point ${key}`, color });

describe('assignAxes', () => {
  const soc = line('1', '%');
  const power = line('2', 'kW');
  const otherPower = line('3', 'kW');
  const flag = line('4', null);

  it('per unit: one axis per unit, alternating sides, in black, grey, dark blue, labelled with its unit', () => {
    const fourth = line('6', 'V');
    const { axes, axisOf } = assignAxes([soc, power, otherPower, flag, fourth], 'per-unit');
    expect(axes.map(axis => [axis.id, axis.side, axis.label, axis.color, axis.keys])).toEqual([
      ['axis-0', 'left', '%', '#111827', ['1']],
      ['axis-1', 'right', 'kW', '#6b7280', ['2', '3']],
      ['axis-2', 'left', '', '#1e3a8a', ['4']], // no unit, no label
      ['axis-3', 'right', 'V', '#111827', ['6']], // the colours repeat
    ]);
    expect(Object.fromEntries(axisOf)).toEqual({ 1: 'axis-0', 2: 'axis-1', 3: 'axis-1', 4: 'axis-2', 6: 'axis-3' });
  });

  it('per unit: points without a unit share an axis', () => {
    const { axes } = assignAxes([flag, power, line('5', null)], 'per-unit');
    expect(axes.map(axis => axis.keys)).toEqual([['4', '5'], ['2']]);
  });

  it('per unit with a single unit: one black axis, its points named', () => {
    const { axes } = assignAxes([power, otherPower], 'per-unit');
    expect(axes).toEqual([{ id: 'axis-0', side: 'left', label: 'kW', names: ['point 2', 'point 3'], color: '#111827', keys: ['2', '3'] }]);
  });

  it('per unit on the dark theme: their light counterparts, so the axes stay readable', () => {
    const { axes } = assignAxes([soc, power, flag], 'per-unit', UNIT_AXIS_COLORS.dark);
    expect(axes.map(axis => axis.color)).toEqual(['#f3f4f6', '#9ca3af', '#60a5fa']);
  });

  it('per unit: every name is kept in full for the legend', () => {
    const names = ['a', 'b', 'c', 'd'].map(key => ({ key, unit: 'kW', label: `inverter_${key}_active_power`, color: '#000' }));
    const [axis] = assignAxes(names, 'per-unit').axes;
    expect(axis.names).toEqual(['inverter_a_active_power', 'inverter_b_active_power', 'inverter_c_active_power', 'inverter_d_active_power']);
  });

  it('per point: each line its own axis, named after it', () => {
    const { axes } = assignAxes([power, otherPower, flag], 'per-point');
    expect(axes.map(axis => [axis.side, axis.label, axis.color])).toEqual([
      ['left', 'point 2 (kW)', '#2'],
      ['right', 'point 3 (kW)', '#3'],
      ['left', 'point 4', '#4'],
    ]);
  });

  it('shared: one axis for everything, labelled only when all share a unit', () => {
    expect(assignAxes([soc, power], 'shared').axes).toEqual([{ id: 'axis-0', side: 'left', label: '', names: ['point 1', 'point 2'], color: undefined, keys: ['1', '2'] }]);
    expect(assignAxes([power, otherPower], 'shared').axes[0].label).toBe('kW');
  });

  it('no lines, no axes', () => {
    expect(assignAxes([], 'per-unit').axes).toEqual([]);
  });
});

describe('isAxisScale', () => {
  it('accepts the three scales only', () => {
    expect(['per-unit', 'per-point', 'shared'].every(isAxisScale)).toBe(true);
    expect(isAxisScale('log')).toBe(false);
    expect(isAxisScale(undefined)).toBe(false);
  });
});

describe('axisWidth', () => {
  it('is as wide as the numbers, so a 1-10 axis is narrower than a 1000-5000 one', () => {
    const small = axisWidth({ min: 1, max: 10 }, false);
    const big = axisWidth({ min: 1000, max: 5000 }, false);
    expect(small).toBeLessThan(big);
    expect(big).toBe(4 * 7 + 10);
  });

  it('adds room for a label only when there is one', () => {
    expect(axisWidth({ min: 1000, max: 5000 }, true) - axisWidth({ min: 1000, max: 5000 }, false)).toBe(16);
  });

  it('leaves room for a top tick that rounds up to the next power of ten', () => {
    expect(axisWidth({ min: 0, max: 9800 }, false)).toBe(5 * 7 + 10); // shows a 10000 tick
  });

  it('has a minimum before any data', () => {
    expect(axisWidth(null, false)).toBe(21 + 10);
  });
});

describe('groupByAxis', () => {
  it('groups legend entries under their axis in axis order, entries on no axis last', () => {
    const { axes, axisOf } = assignAxes([line('1', '%'), line('2', 'kW'), line('3', '%')], 'per-unit');
    const entries = ['2', 'state', '3', '1'].map(key => ({ dataKey: key }));
    const groups = groupByAxis(entries, entry => entry.dataKey, axes, axisOf);
    expect(groups.map(group => [group.axis?.label ?? null, group.entries.map(entry => entry.dataKey)])).toEqual([
      ['%', ['3', '1']],
      ['kW', ['2']],
      [null, ['state']],
    ]);
  });

  it('leaves out an axis with no entries', () => {
    const { axes, axisOf } = assignAxes([line('1', '%'), line('2', 'kW')], 'per-unit');
    expect(groupByAxis([{ dataKey: '2' }], entry => entry.dataKey, axes, axisOf).map(group => group.axis?.id)).toEqual(['axis-1']);
  });
});

describe('valueRange', () => {
  it('spans the given lines, skipping gaps', () => {
    const lines = {
      a: [{ timestamp: 1, a: 3 }, { timestamp: 2, a: null }, { timestamp: 3, a: -2 }],
      b: [{ timestamp: 1, b: 40 }],
    };
    expect(valueRange(lines, ['a'])).toEqual({ min: -2, max: 3 });
    expect(valueRange(lines, ['a', 'b'])).toEqual({ min: -2, max: 40 });
    expect(valueRange(lines, ['missing'])).toBeNull();
  });
});

describe('axisWidth for small ranges', () => {
  it('allows for the decimals Recharts shows', () => {
    expect(axisWidth({ min: 0, max: 2 }, false)).toBe(3 * 7 + 10); // "1.5"
    expect(axisWidth({ min: 0.1, max: 0.3 }, false)).toBe(4 * 7 + 10); // "0.25"
  });
});
