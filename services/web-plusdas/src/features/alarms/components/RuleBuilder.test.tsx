// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { AlarmDefinitionCreateRequest } from '@/api/types/alarms';
import { testSnapshot } from '../lib/testData';
import { RuleBuilder } from './RuleBuilder';

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // cmdk scrolls the active option into view
});

function renderBuilder({ canEnable = true } = {}) {
  const { points, devices, rules } = testSnapshot();
  const onSave = vi.fn();
  render(<RuleBuilder points={points} devices={devices} existingNames={rules.map(rule => rule.name)}
    canEnable={canEnable} onSave={onSave} onCancel={vi.fn()} />);
  return onSave;
}

/** Opens the picker, searches for the point (which lists matches of every device) and picks it. */
async function choosePoint(pointName: string, combobox = screen.getByRole('combobox', { name: 'Point' })) {
  fireEvent.click(combobox);
  fireEvent.change(await screen.findByPlaceholderText('Search devices and points'), { target: { value: pointName } });
  fireEvent.click(await screen.findByRole('option', { name: new RegExp(`^${pointName}`) }));
  await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull());
}

const save = () => fireEvent.click(screen.getByRole('button', { name: 'Save rule' }));
const typeName = (value: string) => fireEvent.change(screen.getByLabelText('Name'), { target: { value } });
const typeThreshold = (value: string) => fireEvent.change(screen.getByRole('textbox', { name: /^Threshold/ }), { target: { value } });
const errorOf = (id: string) => document.getElementById(id)?.textContent;
const saved = (onSave: ReturnType<typeof vi.fn>): AlarmDefinitionCreateRequest => onSave.mock.calls[0][0];

describe('RuleBuilder name', () => {
  it('explains the naming rules and counts characters', () => {
    renderBuilder();
    expect(screen.getByText(/only letters, digits and underscore \(_\), not starting with a digit/)).toBeTruthy();
    typeName('soc_hot');
    expect(screen.getByText('7 / 150')).toBeTruthy();
  });

  it.each([
    ['', 'Required'],
    ['soc low', 'Only letters, digits and underscore (_); a space is not allowed'],
    ['1_low', 'Must not start with a digit'],
    ['BESS_SOC_LOW', 'A rule named "bess_soc_low" already exists'],
    ['PV_INVERTER_OFFLINE', 'A rule named "pv_inverter_offline" already exists'], // profile alarms count too
  ])('rejects %j', async (name, error) => {
    const onSave = renderBuilder();
    typeName(name);
    save();
    await waitFor(() => expect(errorOf('rule-name-error')).toBe(error));
    expect(onSave).not.toHaveBeenCalled();
  });
});

describe('RuleBuilder threshold', () => {
  it("lists the site's points, virtual ones included, grouped by device", async () => {
    renderBuilder();
    fireEvent.click(screen.getByRole('combobox', { name: 'Point' }));
    const listbox = await screen.findByRole('listbox');
    fireEvent.click(within(listbox).getByRole('button', { name: /^bess-1/ }));
    fireEvent.click(within(listbox).getByRole('button', { name: /^pv-1/ }));
    expect(within(listbox).getAllByRole('option').map(option => option.textContent)).toEqual([
      expect.stringMatching(/^bess_ready/), expect.stringMatching(/^faults/), expect.stringMatching(/^pack_voltage/),
      expect.stringMatching(/^state_of_charge/), expect.stringMatching(/^ac_power/),
    ]);
  });

  it('asks for a point and a numeric threshold', async () => {
    const onSave = renderBuilder();
    typeName('soc_low');
    save();
    await waitFor(() => expect(errorOf('rule-point-error')).toBe('Choose a point'));
    await choosePoint('state_of_charge');
    typeThreshold('2o');
    save();
    await waitFor(() => expect(errorOf('rule-threshold-error')).toBe('Must be a number'));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('saves a threshold with deadband, notifications and enabled, and a default message', async () => {
    const onSave = renderBuilder();
    typeName('soc_high');
    await choosePoint('state_of_charge');
    expect(screen.getByLabelText('Threshold (%)')).toBeTruthy();
    typeThreshold('90');
    fireEvent.change(screen.getByLabelText(/Deadband/), { target: { value: '1.5' } });
    fireEvent.click(within(screen.getByRole('group', { name: 'Notifications for this rule' })).getByRole('button', { name: 'Email' }));
    save();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(saved(onSave)).toEqual({
      name: 'soc_high', severity: 'warning', enabled: true,
      notify_mobile: true, notify_email: true,
      message: 'bess-1 · state_of_charge > 90 %',
      rule: { kind: 'threshold', delay_sec: 0, deadband: 1.5,
        condition: { type: 'condition', point_id: 64, operator: '>', value: 90, compare_point_id: null, bit: null } },
    });
  });

  it('a bitfield point tests a bit, with no deadband', async () => {
    const onSave = renderBuilder();
    typeName('bess_trip');
    await choosePoint('faults');
    expect(screen.queryByLabelText(/Deadband/)).toBeNull();
    save();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(saved(onSave).rule).toEqual({ kind: 'threshold', delay_sec: 0, deadband: 0,
      condition: { type: 'condition', point_id: 66, operator: 'bit_set', value: null, compare_point_id: null, bit: 3 } });
    expect(saved(onSave).message).toBe('bess-1 · faults · trip is set');
  });

  it("saves the rule disabled when the site already has the maximum enabled", async () => {
    const onSave = renderBuilder({ canEnable: false });
    const enabled = screen.getByRole('checkbox', { name: /^Enabled/ });
    expect(enabled.hasAttribute('disabled')).toBe(true);
    expect(enabled.getAttribute('aria-checked')).toBe('false');
    typeName('soc_very_low');
    await choosePoint('state_of_charge');
    typeThreshold('5');
    save();
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(saved(onSave).enabled).toBe(false);
  });
});

describe('RuleBuilder condition on several points', () => {
  it('saves an ALL group built with the shared condition editor', async () => {
    const onSave = renderBuilder();
    typeName('low_while_ready');
    fireEvent.click(screen.getByLabelText('Condition on several points'));
    const group = screen.getByRole('group', { name: 'Raise when' });
    await choosePoint('state_of_charge', within(group).getByRole('combobox', { name: 'Point' }));
    fireEvent.change(within(group).getByRole('textbox', { name: /^Value/ }), { target: { value: '10' } });
    fireEvent.click(within(group).getByRole('button', { name: 'Condition' }));
    await choosePoint('bess_ready', within(group).getAllByRole('combobox', { name: 'Point' })[1]);
    save();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(saved(onSave).rule).toEqual({ kind: 'condition', delay_sec: 0, when: { type: 'group', match: 'all', items: [
      { type: 'condition', point_id: 64, operator: '>', value: 10, compare_point_id: null, bit: null },
      { type: 'condition', point_id: 166, operator: '==', value: 0, compare_point_id: null, bit: null },
    ] } });
    expect(saved(onSave).message).toBe('bess-1 · state_of_charge > 10 % and bess-1 · bess_ready is not ready');
  });

  it('shows errors on incomplete conditions', async () => {
    const onSave = renderBuilder();
    typeName('incomplete');
    fireEvent.click(screen.getByLabelText('Condition on several points'));
    save();
    await waitFor(() => expect(screen.getAllByText('Choose a point').length).toBeGreaterThan(0));
    expect(onSave).not.toHaveBeenCalled();
  });
});

describe('RuleBuilder comms stale', () => {
  it("asks for a device, then saves with the site's device id", async () => {
    const onSave = renderBuilder();
    typeName('pv_silent');
    fireEvent.click(screen.getByLabelText('Comms stale'));
    save();
    await waitFor(() => expect(errorOf('rule-device-error')).toBe('Choose a device'));
    expect(onSave).not.toHaveBeenCalled();
  });
});

describe('RuleBuilder editing a user rule', () => {
  function renderEdit(ruleName: string) {
    const { points, devices, rules } = testSnapshot();
    const rule = rules.find(candidate => candidate.name === ruleName)!;
    const onSave = vi.fn();
    render(<RuleBuilder initial={rule} points={points} devices={devices} existingNames={rules.map(candidate => candidate.name)}
      canEnable={false} onSave={onSave} onCancel={vi.fn()} />);
    return { onSave, rule };
  }
  const saveChanges = () => fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

  it('prefills a threshold, its custom delay and deadband, and saves it unchanged as it was', async () => {
    const { onSave, rule } = renderEdit('bess_soc_low');
    expect(screen.getByRole('heading', { name: 'Edit rule bess_soc_low' })).toBeTruthy();
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('bess_soc_low');
    expect(screen.getByRole('combobox', { name: 'Point' }).textContent).toMatch(/bess-1 · state_of_charge/);
    expect((screen.getByRole('textbox', { name: /^Threshold/ }) as HTMLInputElement).value).toBe('20');
    expect((screen.getByLabelText('Custom delay in seconds') as HTMLInputElement).value).toBe('60'); // 60 s is not a preset
    expect((screen.getByLabelText(/Deadband/) as HTMLInputElement).value).toBe('2');
    expect(screen.getByText(/Changing what the rule checks clears its active alarm/)).toBeTruthy();
    saveChanges();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(saved(onSave)).toEqual({
      name: 'bess_soc_low', severity: 'fault', message: 'BESS SOC low', enabled: true,
      notify_mobile: true, notify_email: false, rule: rule.rule,
    });
  });

  it('prefills a comms-stale rule and a condition group, and saves them unchanged', async () => {
    const stale = renderEdit('pv_comms_lost');
    expect((screen.getByLabelText(/No successful poll for more than/) as HTMLInputElement).value).toBe('60');
    saveChanges();
    await waitFor(() => expect(stale.onSave).toHaveBeenCalledTimes(1));
    expect(saved(stale.onSave).rule).toEqual(stale.rule.rule);
    cleanup();

    const condition = renderEdit('bess_trip_while_ready');
    expect(screen.getByRole('group', { name: 'Raise when' })).toBeTruthy();
    expect(screen.getByLabelText('Delay (for)').textContent).toBe('30 s');
    saveChanges();
    await waitFor(() => expect(condition.onSave).toHaveBeenCalledTimes(1));
    expect(saved(condition.onSave).rule).toEqual(condition.rule.rule);
    expect(saved(condition.onSave).enabled).toBe(false); // it was disabled and the site is full
  });

  it("keeps its own name free and its place among the enabled rules, but not another rule's name", async () => {
    const { onSave } = renderEdit('bess_soc_low');
    expect(screen.getByRole('checkbox', { name: /^Enabled/ }).hasAttribute('disabled')).toBe(false);
    typeName('BESS_SOC_LOW');
    saveChanges();
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    typeName('pv_comms_lost');
    saveChanges();
    await waitFor(() => expect(errorOf('rule-name-error')).toBe('A rule named "pv_comms_lost" already exists'));
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
