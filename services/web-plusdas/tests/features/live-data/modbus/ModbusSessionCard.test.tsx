// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { modbusStreamApi } from '@/api';
import type { ModbusRegisterSnapshot } from '@/api/types/modbusStream';
import type { ModbusSessionState } from '@/features/live-data/types';
import { ModbusSessionCard } from '@/features/live-data/modbus/ModbusSessionCard';

const baseSession: ModbusSessionState = {
  sessionId: 'session-1',
  slot: 1,
  viewMode: 'snapshot',
  host: 'mock-modbus',
  port: 502,
  server_address: 1,
  kind: 'holding',
  start_address: 1,
  end_address: 3,
  modbus_address_mode: 'one_based',
  interval: 1,
  duration: 30,
  serverStatus: 'active',
  attachment: 'streaming',
  pollCount: 0,
  lastTimestamp: null,
  registers: {},
  registerConfigs: { '2': { data_type: 'uint16', label: 'pv_array_voltage' } },
  error: null,
  startedAt: null,
};

const twoPolls: ModbusRegisterSnapshot = {
  timestamps: ['2026-09-27T07:00:02Z', '2026-09-27T07:00:01Z'],
  registers: [
    { address: 1, values: [4, 2], label: 'unknown', data_type: 'int16' },
    { address: 2, values: [3401, 3400], label: 'unknown', data_type: 'uint16' },
    { address: 3, values: [5010, null], label: 'unknown', data_type: 'int16' },
  ],
};

const cell = (rowIndex: number, key: string) =>
  document.querySelector(`[data-cell="${rowIndex}:${key}"]`)?.textContent;

function renderCard(session: Partial<ModbusSessionState> = {}) {
  const callbacks = { onResume: vi.fn(), onStop: vi.fn(), onDelete: vi.fn() };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ModbusSessionCard session={{ ...baseSession, ...session }} {...callbacks} />
    </QueryClientProvider>,
  );
  return callbacks;
}

describe('ModbusSessionCard in snapshot view', () => {
  it('always shows 10 poll columns, oldest first from the left, with None where there is no value', async () => {
    vi.spyOn(modbusStreamApi, 'getSnapshot').mockResolvedValue(twoPolls); // newest first from the API
    renderCard();

    // The oldest poll fills the first column, the newest the next one.
    await waitFor(() => expect(cell(0, 'poll_0')).toBe('2'));
    expect(cell(0, 'poll_1')).toBe('4');
    expect(cell(2, 'poll_0')).toBe('None'); // the oldest poll had no value for address 3
    expect(cell(2, 'poll_1')).toBe('5010');
    // First header row (the second holds the filters): "#" + address/label/type + 10 polls.
    const headers = [...document.querySelector('thead tr')!.children].map(th => th.textContent);
    expect(headers).toHaveLength(1 + 3 + 10);
    expect(headers[4]).toBe(new Date(twoPolls.timestamps[1]).toLocaleTimeString());
    expect(headers[5]).toBe(new Date(twoPolls.timestamps[0]).toLocaleTimeString());
    expect(headers[6]).toBe('—');
    expect(cell(1, 'label')).toBe('pv_array_voltage');
    expect(cell(0, 'poll_2')).toBe('None');
    expect(cell(0, 'poll_9')).toBe('None');
  });

  it('lists the session range with None when no poll was recorded yet', async () => {
    vi.spyOn(modbusStreamApi, 'getSnapshot').mockResolvedValue({ timestamps: [], registers: [] });
    renderCard();

    await waitFor(() => expect(cell(2, 'address')).toBe('3'));
    expect(cell(0, 'address')).toBe('1');
    expect(cell(1, 'poll_0')).toBe('None');
  });

  it('fetches once, then only when Take Snapshot is clicked', async () => {
    const getSnapshot = vi.spyOn(modbusStreamApi, 'getSnapshot').mockResolvedValue(twoPolls);
    renderCard();
    await screen.findByRole('button', { name: 'Take Snapshot' }); // enabled once the first fetch settles
    expect(getSnapshot).toHaveBeenCalledTimes(1);

    await new Promise(resolve => setTimeout(resolve, 1500)); // longer than the 1 s poll interval
    expect(getSnapshot).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Take Snapshot' }));
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(2));
    expect(getSnapshot).toHaveBeenCalledWith('session-1');
  });

  it('offers Take Snapshot and Delete, not Resume or Stop', async () => {
    vi.spyOn(modbusStreamApi, 'getSnapshot').mockResolvedValue(twoPolls);
    renderCard();

    expect(await screen.findByRole('button', { name: 'Take Snapshot' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Resume' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull();
  });
});

describe('ModbusSessionCard in live view', () => {
  it('offers Resume, Stop and Delete and never calls the snapshot endpoint', () => {
    const getSnapshot = vi.spyOn(modbusStreamApi, 'getSnapshot');
    renderCard({ viewMode: 'live' });

    expect(screen.getByRole('button', { name: 'Resume' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Take Snapshot' })).toBeNull();
    expect(getSnapshot).not.toHaveBeenCalled();
  });
});
