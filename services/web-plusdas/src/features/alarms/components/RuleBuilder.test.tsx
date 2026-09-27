// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { createMockAlarmSource } from '@/mocks/alarms/mockAlarmSource';
import { ANCHOR } from '@/mocks/alarms/signals';
import type { Rule } from '../types';
import { RuleBuilder } from './RuleBuilder';

async function renderBuilder() {
  const { devices, points, rules } = await createMockAlarmSource({ now: () => ANCHOR }).getSnapshot();
  const onSave = vi.fn();
  render(
    <RuleBuilder devices={devices} points={points} existingNames={rules.map(rule => rule.name)}
      defaultPointId="t1.top_oil_temp" onSave={onSave} onCancel={vi.fn()} />,
  );
  return onSave;
}

const save = () => fireEvent.click(screen.getByRole('button', { name: 'Save rule' }));
const typeName = (value: string) => fireEvent.change(screen.getByLabelText('Name'), { target: { value } });
const typeThreshold = (value: string) => fireEvent.change(screen.getByLabelText(/^Threshold \(/), { target: { value } });
const errorOf = (id: string) => document.getElementById(id)?.textContent;

describe('RuleBuilder name', () => {
  it('explains the naming rules and counts characters', async () => {
    await renderBuilder();
    expect(screen.getByText(/only letters, digits and underscore \(_\), not starting with a digit/)).toBeTruthy();
    typeName('t1_hot');
    expect(screen.getByText('6 / 150')).toBeTruthy();
    expect(screen.getByLabelText('Name').getAttribute('maxLength')).toBe('150');
  });

  it('requires a name', async () => {
    const onSave = await renderBuilder();
    typeThreshold('80');
    save();
    await waitFor(() => expect(errorOf('rule-name-error')).toBe('Required'));
    expect(screen.getByLabelText('Name').getAttribute('aria-invalid')).toBe('true');
    expect(onSave).not.toHaveBeenCalled();
  });

  it.each([
    ['t1 hot', 'Only letters, digits and underscore (_); a space is not allowed'],
    ['1_hot', 'Must not start with a digit'],
    ['T1_TOP_OIL_TEMP_HIGH', 'A rule named "t1_top_oil_temp_high" already exists'],
  ])('rejects %j', async (name, error) => {
    const onSave = await renderBuilder();
    typeName(name);
    typeThreshold('80');
    save();
    await waitFor(() => expect(errorOf('rule-name-error')).toBe(error));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('re-checks the name while typing after a failed save', async () => {
    await renderBuilder();
    typeName('t1 hot');
    save();
    await waitFor(() => expect(errorOf('rule-name-error')).toMatch(/a space is not allowed/));
    typeName('t1_hot');
    expect(errorOf('rule-name-error')).toBeUndefined();
  });
});

describe('RuleBuilder threshold', () => {
  it('shows an error beside an empty threshold and does not save', async () => {
    const onSave = await renderBuilder();
    typeName('t1_hot');
    save();
    await waitFor(() => expect(errorOf('rule-threshold-error')).toBe('Required'));
    expect(screen.getByLabelText(/^Threshold \(/).getAttribute('aria-invalid')).toBe('true');
    expect(onSave).not.toHaveBeenCalled();
  });

  it('rejects a non-numeric threshold', async () => {
    const onSave = await renderBuilder();
    typeName('t1_hot');
    typeThreshold('8o');
    save();
    await waitFor(() => expect(errorOf('rule-threshold-error')).toBe('Must be a number'));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('saves a valid threshold rule under the typed name', async () => {
    const onSave = await renderBuilder();
    typeName('t1_hot');
    typeThreshold('80');
    fireEvent.change(screen.getByLabelText(/Deadband/), { target: { value: '1.5' } });
    save();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const rule: Rule = onSave.mock.calls[0][0];
    expect(rule).toMatchObject({
      name: 't1_hot', type: 'threshold', pointId: 't1.top_oil_temp', operator: '>', threshold: 80, delaySec: 0,
      deadband: 1.5, severity: 'warning', enabled: true, notify: { mobile: true, email: false },
      message: 'Transformer T1: Top-oil temperature > 80 °C',
    });
  });

  it('saves both notification channels when both are selected', async () => {
    const onSave = await renderBuilder();
    typeName('t1_hot');
    typeThreshold('80');
    const group = screen.getByRole('group', { name: 'Notifications for this rule' });
    fireEvent.click(within(group).getByRole('button', { name: 'Email' })); // mobile is on by default
    save();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave.mock.calls[0][0].notify).toEqual({ mobile: true, email: true });
  });

  it('asks for a device for a comms-stale rule', async () => {
    const onSave = await renderBuilder();
    typeName('t2_silent');
    fireEvent.click(screen.getByLabelText('Comms stale'));
    save();
    await waitFor(() => expect(errorOf('rule-device-error')).toBe('Choose a device'));
    expect(onSave).not.toHaveBeenCalled();
  });
});
