// @vitest-environment jsdom
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { alarmsApi, devicesApi, historianApi, sitesApi } from '@/api';
import type { AlarmDefinitionRecord, AlarmDefinitionUpdateRequest } from '@/api/types/alarms';
import type { Site } from '@/api/types/sites';
import AlarmsPage from '@/features/alarms/AlarmsPage';
import { DEVICE_RECORDS, LATEST, SNAPSHOT_RECORD } from '@/features/alarms/lib/testData';

// A stateful stand-in for backend-ot: updates and deletes change what the next snapshot returns.
let definitions: AlarmDefinitionRecord[];

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // Radix Select scrolls the chosen option into view
});

beforeEach(() => {
  vi.restoreAllMocks();
  definitions = structuredClone(SNAPSHOT_RECORD.definitions);
  vi.spyOn(sitesApi, 'getAll').mockResolvedValue([
    { id: '1001', name: 'Alpha Solar Farm' }, { id: '2002', name: 'Beta Yard' },
  ] as Site[]);
  vi.spyOn(alarmsApi, 'getSnapshot').mockImplementation(async siteId => (siteId === '1001'
    ? { ...SNAPSHOT_RECORD, definitions: structuredClone(definitions) }
    : { site_id: 2002, now: SNAPSHOT_RECORD.now, definitions: [], events: [], log: [] }));
  vi.spyOn(devicesApi, 'getRecords').mockImplementation(async siteId => (siteId === '1001' ? DEVICE_RECORDS : []));
  vi.spyOn(historianApi, 'getLatestReadings').mockImplementation(async (_siteId, deviceId) => LATEST.get(Number(deviceId))!);
  vi.spyOn(historianApi, 'getDevicePointReadings').mockResolvedValue({ meta: {}, readings: {} } as never);
  vi.spyOn(alarmsApi, 'update').mockImplementation(async (_siteId, alarmId, patch: AlarmDefinitionUpdateRequest) => {
    definitions = definitions.map(definition => (definition.id === alarmId ? { ...definition, ...patch } as AlarmDefinitionRecord : definition));
    return definitions.find(definition => definition.id === alarmId)!;
  });
  vi.spyOn(alarmsApi, 'remove').mockImplementation(async (_siteId, alarmId) => {
    const removed = definitions.find(definition => definition.id === alarmId)!;
    definitions = definitions.filter(definition => definition.id !== alarmId);
    return removed;
  });
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><AlarmsPage /></QueryClientProvider>);
}

const activeAlarms = () => screen.getByRole('region', { name: 'Active alarms' });
const alarmRow = (deviceName: string) => within(activeAlarms()).getByRole('cell', { name: deviceName }).closest('tr')!;
const deviceHeading = () => screen.getByRole('heading', { level: 2, name: /^(bess-1|pv-1)$/ });
async function openRules() {
  fireEvent.click(screen.getByRole('button', { name: /^Rules \(/ }));
  return screen.findByRole('dialog');
}
const ruleRow = (dialog: HTMLElement, name: string) => within(dialog).getByText(name).closest('tr')!;

describe('AlarmsPage', () => {
  it("summarizes the first site's alarms, lists the active ones and opens on the worst device", async () => {
    renderPage();
    expect(await screen.findByText('1 active fault')).toBeTruthy();
    expect(screen.getByText('1 active warning')).toBeTruthy();
    expect(screen.getByText('0 of 2 devices normal')).toBeTruthy();
    expect(within(activeAlarms()).getAllByRole('row')).toHaveLength(3); // header + bess_soc_low + pv_inverter_offline
    expect(deviceHeading().textContent).toBe('bess-1');
    expect(screen.getByText('Modbus · mock-modbus:502 · unit 2')).toBeTruthy();
    expect(alarmsApi.getSnapshot).toHaveBeenCalledWith('1001');
  });

  it("shows the device's trend and its events of the last 6 h, without a points table or full-history link", async () => {
    renderPage();
    await screen.findByText('1 active fault');
    const device = screen.getByRole('region', { name: 'bess-1' });
    expect(within(device).getByRole('heading', { level: 3, name: 'Events, last 6 h' })).toBeTruthy();
    expect(within(device).getByText('BESS SOC low')).toBeTruthy();
    expect(within(device).queryByRole('heading', { name: 'Points' })).toBeNull();
    expect(within(device).queryByRole('button', { name: 'Query full history' })).toBeNull();
    expect(within(device).queryAllByRole('table')).toHaveLength(0);
  });

  it('opens the alarm device with its point in the trend when an alarm row is clicked', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    fireEvent.click(screen.getByRole('option', { name: /pv-1/ }));
    expect(deviceHeading().textContent).toBe('pv-1');
    expect(screen.getByText('No successful poll stored')).toBeTruthy();

    fireEvent.click(alarmRow('bess-1'));
    expect(deviceHeading().textContent).toBe('bess-1');
    expect(screen.getByRole('heading', { level: 3, name: /^state_of_charge/ })).toBeTruthy();
  });

  it('opens the trend on a point that has readings when the device has no alarming or ruled point', async () => {
    definitions = definitions.filter(definition => definition.id !== 1); // no rule on state_of_charge
    const bessLatest = structuredClone(LATEST.get(2)!);
    delete bessLatest.readings['65']; // pack_voltage, the first numeric point, has no reading
    vi.mocked(historianApi.getLatestReadings).mockImplementation(async (_siteId, deviceId) =>
      (deviceId === '2' ? bessLatest : LATEST.get(Number(deviceId))!));
    renderPage();
    await screen.findByText('0 active faults');
    fireEvent.click(screen.getByRole('option', { name: /bess-1/ }));
    await waitFor(() => expect(screen.getByRole('heading', { level: 3, name: /^state_of_charge/ })).toBeTruthy());
  });

  it("saves a notification change to the alarm, so the rules dialog shows it too", async () => {
    renderPage();
    await screen.findByText('1 active fault');
    fireEvent.click(within(alarmRow('bess-1')).getByRole('button', { name: 'Email' }));

    await waitFor(() => expect(alarmsApi.update).toHaveBeenCalledWith('1001', 1, { notify_mobile: true, notify_email: true }));
    await waitFor(() => expect(within(alarmRow('bess-1')).getByRole('button', { name: 'Email' }).getAttribute('aria-pressed')).toBe('true'));
    const dialog = await openRules();
    const group = within(dialog).getByRole('group', { name: 'Notifications for bess_soc_low' });
    expect(within(group).getByRole('button', { name: 'Email' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('turns off every notification from the rules dialog after confirming', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    const dialog = await openRules();
    expect(within(dialog).getByText(/1 of 4 rules send notifications/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Turn off all notifications' }));
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Turn off' }));

    await waitFor(() => expect(within(dialog).getByText(/0 of 4 rules send notifications/)).toBeTruthy());
    expect(alarmsApi.update).toHaveBeenCalledWith('1001', 1, { notify_mobile: false, notify_email: false });
  });

  it('shows every rule in full, with the profile alarm read-only', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    const dialog = await openRules();

    const soc = ruleRow(dialog, 'bess_soc_low');
    expect(within(soc).getByText('User')).toBeTruthy();
    expect(within(soc).getByText('Threshold')).toBeTruthy();
    expect(within(soc).getByText('bess-1 · state_of_charge < 20 % for 1 min')).toBeTruthy();
    expect(within(soc).getByText('Message: BESS SOC low')).toBeTruthy();
    expect(within(soc).getByText('Delay 60 s')).toBeTruthy();
    expect(within(soc).getByText('Deadband 2')).toBeTruthy();
    expect(within(soc).getByRole('button', { name: 'Delete bess_soc_low' })).toBeTruthy();

    const condition = ruleRow(dialog, 'bess_trip_while_ready');
    expect(within(condition).getByText('bess-1 · faults · trip is set and bess-1 · bess_ready is ready for 30 s')).toBeTruthy();

    const profile = ruleRow(dialog, 'pv_inverter_offline');
    expect(within(profile).getByText('Site profile')).toBeTruthy();
    expect(within(profile).getByText('inverter_offline')).toBeTruthy();
    expect(within(profile).queryByRole('button', { name: /^Delete/ })).toBeNull();
    expect(within(profile).queryByRole('button', { name: /^Edit/ })).toBeNull();
    expect(within(profile).getAllByRole('cell').at(-1)!.innerHTML).toBe(''); // no greyed-out bin either
  });

  it('enables a disabled rule from the rules dialog, with no separate Shown switch', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    const dialog = await openRules();
    expect(within(dialog).queryByRole('columnheader', { name: 'Shown' })).toBeNull();
    expect(within(dialog).getByText(/3 of 20 now/)).toBeTruthy();
    fireEvent.click(within(ruleRow(dialog, 'bess_trip_while_ready')).getByRole('switch', { name: 'Enable bess_trip_while_ready' }));

    await waitFor(() => expect(alarmsApi.update).toHaveBeenCalledWith('1001', 4, { enabled: true }));
    await waitFor(() => expect(within(dialog).getByText(/4 of 20 now/)).toBeTruthy());
  });

  it('flips a switch at once while saving, and puts it back when the save fails', async () => {
    let rejectSave: (error: unknown) => void = () => {};
    vi.mocked(alarmsApi.update).mockImplementation(() => new Promise((_resolve, reject) => { rejectSave = reject; }));
    renderPage();
    await screen.findByText('1 active fault');
    const dialog = await openRules();
    const enabled = () => within(ruleRow(dialog, 'bess_soc_low')).getByRole('switch', { name: /bess_soc_low$/ });
    expect(enabled().getAttribute('aria-checked')).toBe('true');

    fireEvent.click(enabled());
    await waitFor(() => expect(enabled().getAttribute('aria-checked')).toBe('false')); // before backend-ot answers
    rejectSave({ detail: { error: 'ConflictError', message: 'nope' } });
    await waitFor(() => expect(enabled().getAttribute('aria-checked')).toBe('true'));
  });

  it('edits a user rule in the prefilled builder and saves it to the alarm', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    const dialog = await openRules();
    expect(within(ruleRow(dialog, 'pv_inverter_offline')).queryByRole('button', { name: /^Edit/ })).toBeNull();
    fireEvent.click(within(ruleRow(dialog, 'bess_soc_low')).getByRole('button', { name: 'Edit bess_soc_low' }));

    expect(await screen.findByRole('heading', { name: 'Edit rule bess_soc_low' })).toBeTruthy();
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.change(screen.getByRole('textbox', { name: /^Threshold/ }), { target: { value: '25' } });
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'SOC under 25 %' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(alarmsApi.update).toHaveBeenCalledWith('1001', 1, expect.objectContaining({
      name: 'bess_soc_low', message: 'SOC under 25 %',
      rule: expect.objectContaining({ kind: 'threshold', condition: expect.objectContaining({ point_id: 64, operator: '<', value: 25 }) }),
    })));
    await waitFor(() => expect(screen.queryByRole('heading', { name: /Edit rule/ })).toBeNull());
    expect((await openRules()).textContent).toContain('bess-1 · state_of_charge < 25 % for 1 min');
  });

  it('deletes a user rule permanently after confirming', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    const dialog = await openRules();
    fireEvent.click(within(ruleRow(dialog, 'pv_comms_lost')).getByRole('button', { name: 'Delete pv_comms_lost' }));
    const confirm = await screen.findByRole('alertdialog');
    expect(within(confirm).getByText(/whole alarm history .* removed permanently/)).toBeTruthy();
    fireEvent.click(within(confirm).getByRole('button', { name: 'Delete permanently' }));

    await waitFor(() => expect(alarmsApi.remove).toHaveBeenCalledWith('1001', 2));
    await waitFor(() => expect(within(dialog).queryByText('pv_comms_lost')).toBeNull());
    expect(within(dialog).getByText('Alarm rules (3)')).toBeTruthy();
  });

  it('switches to another site', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    fireEvent.click(screen.getByLabelText('Site'));
    fireEvent.click(await screen.findByRole('option', { name: 'Beta Yard' }));

    await waitFor(() => expect(alarmsApi.getSnapshot).toHaveBeenCalledWith('2002'));
    expect(await screen.findByText('This site has no devices.')).toBeTruthy();
    expect(screen.getByText('0 active faults')).toBeTruthy();
  });
});
