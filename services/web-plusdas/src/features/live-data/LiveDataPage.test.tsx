// @vitest-environment jsdom
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi, historianApi, modbusStreamApi, sitesApi } from '@/api';
import type { DevicePoint } from '@/api/types/devicePoints';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { BackendPointReadings } from '@/api/types/historian';
import type { Site } from '@/api/types/sites';
import LiveData from './LiveDataPage';

// Not under test: the notes sidebar (kept collapsed) and the signed-in user the Modbus Debug tab reads.
vi.mock('@/shared/contexts/NotesSidebarContext', () => ({
  useNotesSidebar: () => ({ isNotesCollapsed: true, setIsNotesCollapsed: () => {} }),
}));
vi.mock('@/shared/contexts/auth', () => ({
  useAuth: () => ({ user: { id: 'u1', name: 'Test', email: 'test@example.com', role: 'admin' } }),
}));

const point = (id: number, name: string, extra: Partial<DevicePoint> = {}) =>
  ({ id, name, category: 'NATIVE', data_type: 'uint16', unit: null, ...extra }) as DevicePoint;

const pvPoints = {
  standardized: [point(1, 'PV_ACTIVE_POWER', { category: 'STANDARDIZED', address: 0, size: 1 })],
  virtual: [point(2, 'SITE_AC_POWER', { category: 'VIRTUAL', unit: 'W', data_type: 'float32', address: 0, size: 2 })],
  native: [
    point(3, 'ac_voltage', { unit: 'V', address: 1001, size: 1, scale_factor: 0.1, poll_kind: 'holding' }),
    point(4, 'inverter_state', { data_type: 'enum16', enum_detail: { '1': 'mppt' }, address: 16, size: 1, poll_kind: 'input' }),
  ],
};
const DEVICES: Record<string, DevicePointsEntry[]> = {
  '1001': [
    { deviceId: 11, deviceName: 'pv-1', groups: pvPoints, points: [...pvPoints.standardized, ...pvPoints.virtual, ...pvPoints.native] },
    { deviceId: 12, deviceName: 'bess-1', groups: { standardized: [], virtual: [], native: [point(5, 'soc')] }, points: [point(5, 'soc')] },
  ],
  '2002': [{ deviceId: 21, deviceName: 'meter-9', groups: { standardized: [], virtual: [], native: [] }, points: [] }],
};

const time = (second: number) => new Date(Date.UTC(2026, 9, 1, 12, 0, second)).toISOString();
const READINGS = {
  meta: {},
  readings: {
    '2': { id: 2, name: 'SITE_AC_POWER', data_type: 'float32', count: 12,
      timeseries: Array.from({ length: 12 }, (_, index) => ({ time: time(55 - index * 5), value: 1000 + index })) },
    '3': { id: 3, name: 'ac_voltage', data_type: 'uint16', count: 2, timeseries: [{ time: time(55), value: 239.5 }, { time: time(50), value: 238 }] },
    '4': { id: 4, name: 'inverter_state', data_type: 'enum16', count: 1, timeseries: [{ time: time(55), value: 1 }] },
  },
} as unknown as BackendPointReadings;

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // Radix Select scrolls the chosen option into view
});

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(sitesApi, 'getAll').mockResolvedValue([{ id: '1001', name: 'Alpha Solar Farm' }, { id: '2002', name: 'Beta Yard' }] as Site[]);
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockImplementation(async siteId => DEVICES[siteId]);
  vi.spyOn(historianApi, 'getRecentReadings').mockResolvedValue(READINGS);
  vi.spyOn(modbusStreamApi, 'list').mockResolvedValue([]);
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><LiveData /></QueryClientProvider>);
}

const deviceList = () => screen.findByRole('listbox', { name: 'Devices' });
const snapshot = () => screen.getByRole('region', { name: 'pv-1' });

describe('Live Data point monitoring', () => {
  it("lists only the site's devices, with no point checkboxes, until a device is chosen", async () => {
    renderPage();
    const list = await deviceList();
    expect(within(list).getAllByRole('option').map(option => option.textContent)).toEqual(['pv-14 points', 'bess-11 points']);
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    expect(screen.getByText('No Device Selected')).toBeTruthy();
    expect(historianApi.getRecentReadings).not.toHaveBeenCalled();
  });

  it("shows every point of the chosen device, grouped, with its register, type, size, scale and last 10 readings", async () => {
    renderPage();
    fireEvent.click(within(await deviceList()).getByRole('option', { name: /pv-1/ }));

    await waitFor(() => expect(within(snapshot()).getAllByRole('columnheader')).toHaveLength(6 + 10));
    expect(historianApi.getRecentReadings).toHaveBeenCalledExactlyOnceWith('1001', '11', 10);
    expect(within(snapshot()).getAllByRole('columnheader').slice(0, 6).map(header => header.textContent))
      .toEqual(['Point', 'Register', 'Type', 'Size', 'Scale', 'Unit']);
    const groupRows = within(snapshot()).getAllByRole('row').map(row => row.textContent).filter(text => /\(\d+\)$/.test(text ?? ''));
    expect(groupRows).toEqual(['Standardized (1)', 'Virtual (1)', 'Native (2)']);

    const cellsOf = (name: string) => within(within(snapshot()).getByText(name).closest('tr')!).getAllByRole('cell').map(cell => cell.textContent);
    // Point, Register (native only), Type, Size, Scale, Unit, then the readings, newest first.
    expect(cellsOf('PV_ACTIVE_POWER')).toEqual(['PV_ACTIVE_POWER', '—', 'uint16', '1', '—', '—', ...Array(10).fill('—')]);
    expect(cellsOf('SITE_AC_POWER').slice(0, 9)).toEqual(['SITE_AC_POWER', '—', 'float32', '2', '—', 'W', '1000', '1001', '1002']);
    expect(cellsOf('ac_voltage').slice(0, 9)).toEqual(['ac_voltage', '1001holding', 'uint16', '1', '0.1', 'V', '239.5', '238', '—']);
    expect(cellsOf('inverter_state').slice(0, 8)).toEqual(['inverter_state', '16input', 'enum16', '1', '—', '—', 'mppt', '—']);
  });

  it('fetches again only when a snapshot is taken', async () => {
    renderPage();
    fireEvent.click(within(await deviceList()).getByRole('option', { name: /pv-1/ }));
    await waitFor(() => expect(historianApi.getRecentReadings).toHaveBeenCalledTimes(1));
    fireEvent.focus(window);

    fireEvent.click(within(snapshot()).getByRole('button', { name: 'Take snapshot' }));
    await waitFor(() => expect(historianApi.getRecentReadings).toHaveBeenCalledTimes(2));
  });

  it('clears the device when the site changes', async () => {
    renderPage();
    fireEvent.click(within(await deviceList()).getByRole('option', { name: /pv-1/ }));
    await waitFor(() => expect(snapshot()).toBeTruthy());

    fireEvent.click(screen.getByLabelText('Site'));
    fireEvent.click(await screen.findByRole('option', { name: 'Beta Yard' }));
    await waitFor(() => expect(within(screen.getByRole('listbox', { name: 'Devices' })).getAllByRole('option').map(option => option.textContent))
      .toEqual(['meter-90 points']));
    expect(screen.getByText('No Device Selected')).toBeTruthy();
  });
});
