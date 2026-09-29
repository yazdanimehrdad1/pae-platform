import { describe, expect, it } from 'vitest';
import {
  describeGroupDraft,
  newCondition,
  newItemKey,
  operatorsFor,
  operatorText,
  validateCondition,
  withPoint,
  type ConditionGroupDraft,
  type ConditionPointOption,
} from './conditionModel';

const power: ConditionPointOption = { id: '1', name: 'power', label: 'dev · power', group: 'dev', kind: 'numeric', unit: 'kW' };
const state: ConditionPointOption = {
  id: '2', name: 'state', label: 'dev · state', group: 'dev', kind: 'enum',
  states: [{ value: 1, label: 'off' }, { value: 2, label: 'running' }],
};
const flags: ConditionPointOption = {
  id: '3', name: 'flags', label: 'dev · flags', group: 'dev', kind: 'bitfield', bits: [{ bit: 3, label: 'relay' }],
};
const pointsById = new Map([power, state, flags].map(point => [point.id, point]));

describe('operatorsFor', () => {
  it('offers comparisons for numbers, is / is not for enums, and bit tests first for bitfields', () => {
    expect(operatorsFor('numeric')).toEqual(['>', '<', '>=', '<=', '==', '!=']);
    expect(operatorsFor('enum')).toEqual(['==', '!=']);
    expect(operatorsFor('bitfield').slice(0, 2)).toEqual(['bit_set', 'bit_clear']);
  });

  it('respects an allowed list', () => {
    expect(operatorsFor('bitfield', ['>', '=='])).toEqual(['>', '==']);
  });

  it('words enum comparisons as is / is not', () => {
    expect(operatorText('==', 'enum')).toBe('is');
    expect(operatorText('!=', 'enum')).toBe('is not');
    expect(operatorText('>=')).toBe('≥');
  });
});

describe('withPoint', () => {
  it('moving onto an enum keeps a fitting operator and picks its first state', () => {
    const moved = withPoint({ ...newCondition('1'), operator: '>', value: '5' }, state);
    expect(moved).toMatchObject({ pointId: '2', operator: '==', value: '1', operand: 'value' });
  });

  it('moving onto a bitfield picks a bit test and its first bit', () => {
    expect(withPoint(newCondition(), flags)).toMatchObject({ pointId: '3', operator: 'bit_set', bit: 3 });
  });

  it('moving from a number onto a bitfield switches to a bit test, but bitfield to bitfield keeps a comparison', () => {
    const onPower = { ...newCondition('1'), operator: '>' as const, value: '5' };
    expect(withPoint(onPower, flags, undefined, power)).toMatchObject({ operator: 'bit_set', bit: 3 });
    const onFlags = { ...newCondition('3'), operator: '>' as const, value: '5' };
    expect(withPoint(onFlags, { ...flags, id: '4' }, undefined, flags)).toMatchObject({ pointId: '4', operator: '>', bit: null });
  });

  it('keeps the operator and value when they still fit', () => {
    expect(withPoint({ ...newCondition('1'), operator: '<=', value: '7' }, power)).toMatchObject({ operator: '<=', value: '7' });
  });
});

describe('validateCondition', () => {
  it('needs a point and a numeric value', () => {
    expect(validateCondition(newCondition())).toEqual({ point: 'Choose a point', value: 'Required' });
    expect(validateCondition({ ...newCondition('1'), value: '8o' })).toEqual({ value: 'Must be a number' });
    expect(validateCondition({ ...newCondition('1'), value: '8' })).toEqual({});
  });

  it('needs a bit for a bit test, and a point when comparing with a point', () => {
    expect(validateCondition({ ...newCondition('3'), operator: 'bit_set', bit: null })).toEqual({ value: 'Choose a bit' });
    expect(validateCondition({ ...newCondition('1'), operand: 'point' })).toEqual({ value: 'Choose a point' });
  });
});

describe('describeGroupDraft', () => {
  it('reads nested groups in plain words', () => {
    const group: ConditionGroupDraft = {
      match: 'all',
      items: [
        { type: 'condition', key: newItemKey(), condition: { ...newCondition('1'), operator: '>=', value: '20' } },
        {
          type: 'group', key: newItemKey(), group: {
            match: 'any',
            items: [
              { type: 'condition', key: newItemKey(), condition: { ...newCondition('2'), operator: '==', value: '2' } },
              { type: 'condition', key: newItemKey(), condition: { ...newCondition('3'), operator: 'bit_set', bit: 3 } },
            ],
          },
        },
      ],
    };
    expect(describeGroupDraft(group, pointsById)).toBe('dev · power ≥ 20 kW and (dev · state is running or dev · flags · relay is set)');
  });
});
