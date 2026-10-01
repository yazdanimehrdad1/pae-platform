// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi, sitesApi } from '@/api';
import type { DevicePoint } from '@/api/types/devicePoints';
import type { Site } from '@/api/types/sites';
import { createMockAlarmSource } from '@/mocks/alarms/mockAlarmSource';
import { ANCHOR } from '@/mocks/alarms/signals';
import type { Rule } from '../types';
import { RuleBuilder } from './RuleBuilder';

const point = (id: number, name: string, extra: Partial<DevicePoint> = {}) =>
  ({ id, name, category: 'NATIVE', data_type: 'uint16', unit: null, ...extra }) as unknown as DevicePoint;

const SITE_POINTS = {
  '1001': [{
    deviceId: 2, deviceName: 'bess-1', groups: { standardized: [], virtual: [], native: [] },
    points: [
      point(64, 'state_of_charge', { unit: '%' }),
      point(66, 'battery_state', { data_type: 'enum16', enum_detail: { '1': 'standby', '5': 'fault' } }),
      point(166, 'BESS_READY', { category: 'VIRTUAL', data_type: 'enum16', enum_detail: { '0': 'not ready', '1': 'ready' } }),
    ],
  }],
  '2002': [{
    deviceId: 9, deviceName: 'meter-9', groups: { standardized: [], virtual: [], native: [] },
    points: [point(90, 'import_power', { unit: 'kW' })],
  }],
};

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // cmdk scrolls the active option into view
});

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(sitesApi, 'getAll').mockResolvedValue([
    { id: '1001', name: 'Alpha Solar Farm' }, { id: '2002', name: 'Beta Yard' },
  ] as Site[]);
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockImplementation(async siteId => SITE_POINTS[siteId as keyof typeof SITE_POINTS]);
});

async function renderBuilder() {
  const { devices, rules } = await createMockAlarmSource({ now: () => ANCHOR }).getSnapshot();
  const onSave = vi.fn();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  render(<RuleBuilder devices={devices} existingNames={rules.map(rule => rule.name)} onSave={onSave} onCancel={vi.fn()} />, { wrapper });
  await waitFor(() => expect(screen.getByLabelText('Site').textContent).toBe('Alpha Solar Farm'));
  return onSave;
}

async function choosePoint(pointName: string) {
  fireEvent.click(screen.getByRole('combobox', { name: 'Point' }));
  fireEvent.click(await screen.findByRole('option', { name: new RegExp(`^${pointName}`) }));
}

const save = () => fireEvent.click(screen.getByRole('button', { name: 'Save rule' }));
const typeName = (value: string) => fireEvent.change(screen.getByLabelText('Name'), { target: { value } });
const typeThreshold = (value: string) => fireEvent.change(screen.getByRole('textbox', { name: /^Threshold/ }), { target: { value } });
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
    await choosePoint('state_of_charge');
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

describe('RuleBuilder threshold on a site device point', () => {
  it('lists the chosen site\'s real device points, virtual ones included, grouped by device', async () => {
    await renderBuilder();
    fireEvent.click(screen.getByRole('combobox', { name: 'Point' }));
    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).getByText('bess-1')).toBeTruthy();
    expect(within(listbox).getAllByRole('option').map(option => option.textContent)).toEqual([
      expect.stringMatching(/^state_of_charge/), expect.stringMatching(/^battery_state/), expect.stringMatching(/^BESS_READY/),
    ]);
    expect(within(listbox).queryByText(/Top-oil temperature/)).toBeNull(); // no mock points
  });

  it('asks for a point before saving', async () => {
    const onSave = await renderBuilder();
    typeName('soc_low');
    typeThreshold('20');
    save();
    await waitFor(() => expect(errorOf('rule-point-error')).toBe('Choose a point'));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('shows an error beside an empty or non-numeric threshold and does not save', async () => {
    const onSave = await renderBuilder();
    typeName('soc_low');
    await choosePoint('state_of_charge');
    save();
    await waitFor(() => expect(errorOf('rule-threshold-error')).toBe('Required'));
    typeThreshold('2o');
    save();
    await waitFor(() => expect(errorOf('rule-threshold-error')).toBe('Must be a number'));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('saves a rule on the device point, with where it lives for display', async () => {
    const onSave = await renderBuilder();
    typeName('soc_low');
    await choosePoint('state_of_charge');
    expect(screen.getByLabelText('Threshold (%)')).toBeTruthy();
    typeThreshold('20');
    fireEvent.change(screen.getByLabelText(/Deadband/), { target: { value: '1.5' } });
    save();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const rule: Rule = onSave.mock.calls[0][0];
    expect(rule).toMatchObject({
      name: 'soc_low', type: 'threshold', pointId: '64', threshold: 20, delaySec: 0, deadband: 1.5,
      target: { siteId: '1001', deviceName: 'bess-1', pointName: 'state_of_charge', unit: '%' },
      severity: 'warning', enabled: true, notify: { mobile: true, email: false },
      message: 'bess-1: state_of_charge > 20 %',
    });
  });

  it('an enum point offers its states and saves the chosen state with its labels', async () => {
    const onSave = await renderBuilder();
    typeName('bess_fault');
    await choosePoint('battery_state');
    expect(screen.getByLabelText('Operator').textContent).toBe('is');
    expect(screen.getByLabelText('Threshold').textContent).toBe('standby');
    save();

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave.mock.calls[0][0]).toMatchObject({
      pointId: '66', operator: '=', threshold: 1,
      target: { states: { 1: 'standby', 5: 'fault' } },
      message: 'bess-1: battery_state = standby',
    });
  });

  it('switching site lists that site\'s points and clears the chosen point', async () => {
    await renderBuilder();
    await choosePoint('state_of_charge');
    fireEvent.click(screen.getByLabelText('Site'));
    fireEvent.click(await screen.findByRole('option', { name: 'Beta Yard' }));

    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Point' }).textContent).toMatch(/Choose a point/));
    fireEvent.click(screen.getByRole('combobox', { name: 'Point' }));
    expect(await screen.findByRole('option', { name: /^import_power/ })).toBeTruthy();
  });

  it('saves both notification channels when both are selected', async () => {
    const onSave = await renderBuilder();
    typeName('soc_low');
    await choosePoint('state_of_charge');
    typeThreshold('20');
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
