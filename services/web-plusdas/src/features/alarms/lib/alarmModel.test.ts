import { describe, expect, it } from 'vitest';
import type { Point, ThresholdRule } from '../types';
import { describeCondition, formatLimit } from './alarmModel';

const base: ThresholdRule = {
  id: 'r1', type: 'threshold', name: 'r1', pointId: '64', operator: '>', threshold: 20, delaySec: 300, deadband: 0,
  severity: 'warning', message: '', enabled: true, notify: { mobile: false, email: false },
};

describe('describeCondition', () => {
  it('describes a rule on a real device point from its target, without a mock point', () => {
    const rule = { ...base, target: { siteId: '1001', deviceName: 'bess-1', pointName: 'state_of_charge', unit: '%' } };
    expect(describeCondition(rule, null)).toBe('state_of_charge > 20 % for 5 min');
  });

  it('labels an enum target\'s state', () => {
    const rule = { ...base, operator: '=' as const, threshold: 5, delaySec: 0,
      target: { siteId: '1001', deviceName: 'bess-1', pointName: 'battery_state', unit: null, states: { 1: 'standby', 5: 'fault' } } };
    expect(formatLimit(rule, null)).toBe('= fault');
  });

  it('still prefers the mock point when there is one', () => {
    const point = { id: '64', name: 'Top-oil temperature', unit: '°C', kind: 'numeric' } as Point;
    expect(describeCondition({ ...base, delaySec: 0 }, point)).toBe('Top-oil temperature > 20 °C');
  });

  it('falls back to the point id with neither', () => {
    expect(describeCondition({ ...base, delaySec: 0 }, null)).toBe('64 > 20');
  });
});
