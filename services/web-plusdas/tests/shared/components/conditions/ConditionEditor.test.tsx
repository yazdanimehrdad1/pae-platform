// @vitest-environment jsdom
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { ConditionGroup } from '@/shared/components/conditions/ConditionGroup';
import { ConditionRow } from '@/shared/components/conditions/ConditionRow';
import { newCondition, newGroup, type ConditionDraft, type ConditionGroupDraft, type ConditionPointOption } from '@/shared/components/conditions/conditionModel';

const points: ConditionPointOption[] = [
  { id: '1', name: 'power', label: 'dev · power', group: 'dev', kind: 'numeric', unit: 'kW' },
  { id: '2', name: 'state', label: 'dev · state', group: 'dev', kind: 'enum', states: [{ value: 1, label: 'off' }, { value: 2, label: 'running' }] },
  { id: '3', name: 'flags', label: 'dev · flags', group: 'dev', kind: 'bitfield', bits: [{ bit: 3, label: 'relay' }] },
];

function renderRow(condition: ConditionDraft, props: Partial<Parameters<typeof ConditionRow>[0]> = {}) {
  const onChange = vi.fn();
  render(<ConditionRow condition={condition} onChange={onChange} points={points} showLabels {...props} />);
  return onChange;
}

describe('ConditionRow', () => {
  it('a numeric point takes a typed value, labelled with its unit', () => {
    const onChange = renderRow({ ...newCondition('1'), value: '5' });
    const input = screen.getByLabelText('Value (kW)');
    fireEvent.change(input, { target: { value: '20' } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ value: '20' }));
  });

  it('an enum point reads "is" and offers its states instead of a number', () => {
    renderRow({ ...newCondition('2'), operator: '==', value: '2' });
    expect(screen.getByLabelText('Operator').textContent).toBe('is');
    expect(screen.getByLabelText('Value').textContent).toBe('running');
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('a bit test on a bitfield offers its labelled bits', () => {
    renderRow({ ...newCondition('3'), operator: 'bit_set', bit: 3 });
    expect(screen.getByLabelText('Operator').textContent).toBe('is set');
    expect(screen.getByLabelText('Bit').textContent).toBe('3 · relay');
  });

  it('can compare with another point only when allowed', () => {
    renderRow({ ...newCondition('1'), value: '5' });
    expect(screen.queryByLabelText('Compare with')).toBeNull();
    screen.getByLabelText('Value (kW)');
  });

  it('compares with a point when the operand is a point', () => {
    renderRow({ ...newCondition('1'), operand: 'point', comparePointId: '2' }, { allowComparePoint: true });
    expect(screen.getByLabelText('Compare with').textContent).toBe('point');
    expect(screen.getByRole('combobox', { name: 'Compare with point' }).textContent).toContain('dev · state');
  });

  it('shows errors beside the fields they belong to', () => {
    renderRow(newCondition(), { errors: { point: 'Choose a point', value: 'Required' }, ids: { point: 'p', value: 'v' } });
    expect(document.getElementById('p-error')?.textContent).toBe('Choose a point');
    expect(document.getElementById('v-error')?.textContent).toBe('Required');
  });
});

function StatefulGroup({ initial }: { initial: ConditionGroupDraft }) {
  const [group, setGroup] = useState(initial);
  return <ConditionGroup group={group} onChange={setGroup} points={points} label="Case 1" />;
}

const rowsIn = (element: HTMLElement) => within(element).queryAllByTestId('condition-row');

describe('ConditionGroup', () => {
  it('adds conditions, and removes them down to one', () => {
    render(<StatefulGroup initial={newGroup()} />);
    const group = screen.getByRole('group', { name: 'Case 1' });
    expect(within(group).queryByRole('button', { name: 'Remove condition' })).toBeNull();

    fireEvent.click(within(group).getByRole('button', { name: 'Condition' }));
    expect(rowsIn(group)).toHaveLength(2);

    fireEvent.click(within(group).getAllByRole('button', { name: 'Remove condition' })[0]);
    expect(rowsIn(group)).toHaveLength(1);
  });

  it('nests one level of groups, and a nested group cannot nest again', () => {
    render(<StatefulGroup initial={newGroup()} />);
    const group = screen.getByRole('group', { name: 'Case 1' });
    fireEvent.click(within(group).getByRole('button', { name: 'Group' }));

    const nested = within(group).getByRole('group', { name: 'Nested group' });
    expect(rowsIn(nested)).toHaveLength(1);
    expect(within(nested).queryByRole('button', { name: 'Group' })).toBeNull();
    expect(within(nested).getByLabelText('Nested group: match').textContent).toBe('ANY');

    fireEvent.click(within(group).getByRole('button', { name: 'Remove nested group' }));
    expect(within(group).queryByRole('group', { name: 'Nested group' })).toBeNull();
  });
});
