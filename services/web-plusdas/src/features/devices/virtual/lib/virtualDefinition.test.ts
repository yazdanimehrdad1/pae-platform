import { describe, expect, it } from 'vitest';
import type { DevicePoint } from '@/api/types/devicePoints';
import type { DevicePointsEntry } from '@/api/types/devices';
import { toConditionPointOptions } from './pointOptions';
import { describeDraft, draftFromPoint, emptyDraft, newInput, toDefinition, validateDraft } from './virtualDefinition';

const conditionPoint = {
  id: 9, name: 'BESS_READY', category: 'VIRTUAL', data_type: 'enum16', unit: null,
  virtual_definition: {
    kind: 'condition',
    cases: [{
      output: 2, label: 'fault',
      when: {
        type: 'group', match: 'any', items: [
          { type: 'condition', point_id: 1, operator: '==', value: 5, compare_point_id: null, bit: null },
          {
            type: 'group', match: 'all', items: [
              { type: 'condition', point_id: 2, operator: 'bit_set', value: null, compare_point_id: null, bit: 7 },
              { type: 'condition', point_id: 3, operator: '>', value: null, compare_point_id: 4, bit: null },
            ],
          },
        ],
      },
    }],
    default_output: 0,
    default_label: 'not ready',
  },
} as unknown as DevicePoint;

describe('draft <-> definition', () => {
  it('round-trips a condition with nested groups, bit tests and point comparisons', () => {
    expect(toDefinition(draftFromPoint(conditionPoint))).toEqual(conditionPoint.virtual_definition);
  });

  it('round-trips a calculation', () => {
    const definition = { kind: 'calculation' as const, function: 'ratio' as const, inputs: [1, 2], scale: 100, offset: 0 };
    const point = { ...conditionPoint, virtual_definition: definition } as DevicePoint;
    const draft = draftFromPoint(point);
    expect(draft.kind).toBe('calculation');
    expect(toDefinition(draft)).toEqual(definition);
  });

  it('sends blank state names as null', () => {
    const draft = draftFromPoint(conditionPoint);
    draft.cases[0].label = '  ';
    const definition = toDefinition(draft);
    expect(definition.kind === 'condition' && definition.cases[0].label).toBeNull();
  });
});

describe('validateDraft', () => {
  it('a new draft needs a name, a point and a value', () => {
    const { errors, isValid } = validateDraft(emptyDraft());
    expect(isValid).toBe(false);
    expect(errors.name).toBe('Required');
    expect(Object.values(errors.conditions)).toEqual([{ point: 'Choose a point', value: 'Required' }]);
  });

  it('outputs are whole numbers within enum16', () => {
    const draft = { ...draftFromPoint(conditionPoint), defaultOutput: '70000' };
    draft.cases[0].output = '1.5';
    const { errors } = validateDraft(draft);
    expect(Object.values(errors.caseOutputs)).toEqual(['A whole number 0-65535']);
    expect(errors.defaultOutput).toBe('A whole number 0-65535');
  });

  it('a calculation needs every input and numeric scale and offset', () => {
    const draft = { ...emptyDraft(), name: 'V', kind: 'calculation' as const, inputs: [newInput('1'), newInput()], scale: 'x' };
    const { errors, isValid } = validateDraft(draft);
    expect(isValid).toBe(false);
    expect(Object.values(errors.inputs)).toEqual(['Choose a point']);
    expect(errors.scale).toBe('Must be a number');
    expect(validateDraft({ ...draft, inputs: [newInput('1'), newInput('2')], scale: '1' }).isValid).toBe(true);
  });

  it('an existing valid point validates', () => {
    expect(validateDraft(draftFromPoint(conditionPoint)).isValid).toBe(true);
  });
});

describe('toConditionPointOptions and describeDraft', () => {
  const devices: DevicePointsEntry[] = [{
    deviceId: 2, deviceName: 'bess', groups: { standardized: [], virtual: [], native: [] },
    points: [
      { id: 1, name: 'battery_state', category: 'NATIVE', data_type: 'enum16', enum_detail: { '5': 'fault', '1': 'standby' } },
      { id: 2, name: 'alarm_flags', category: 'NATIVE', data_type: 'bitfield16', bitfield_detail: { '7': 'bms_err' } },
      { id: 3, name: 'soc', category: 'NATIVE', data_type: 'uint16', unit: '%' },
      { id: 4, name: 'soc_min', category: 'STANDARDIZED', data_type: 'uint16', unit: '%' },
      { id: 9, name: 'BESS_READY', category: 'VIRTUAL', data_type: 'enum16' },
    ] as unknown as DevicePoint[],
  }];
  const options = toConditionPointOptions(devices);

  it('offers every non-virtual point with its kind, states and bits', () => {
    expect(options.map(option => [option.id, option.kind])).toEqual([['1', 'enum'], ['2', 'bitfield'], ['3', 'numeric'], ['4', 'numeric']]);
    expect(options[0].states).toEqual([{ value: 1, label: 'standby' }, { value: 5, label: 'fault' }]);
    expect(options[1].bits).toEqual([{ bit: 7, label: 'bms_err' }]);
    expect(options[3].hint).toBe('standardized');
  });

  it('summarises a condition case by case', () => {
    const pointsById = new Map(options.map(option => [option.id, option]));
    expect(describeDraft(draftFromPoint(conditionPoint), pointsById)).toEqual([
      'If bess · battery_state is fault or (bess · alarm_flags · bms_err is set and bess · soc > bess · soc_min) → 2 "fault"',
      'Otherwise → 0 "not ready"',
    ]);
  });
});
