// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ModbusLiveStreamRequest } from '@/shared/types/modbusLiveStream';
import { ModbusStreamForm } from './ModbusStreamForm';

const request = {
  host: 'mock-modbus',
  port: 502,
  server_address: 1,
  kind: 'holding',
  start_address: 0,
  end_address: 2,
  modbus_address_mode: 'zero_based',
  interval: 1,
  duration: 300,
  byte_order: 'big',
  word_order: 'msw_first',
  register_configs: { '1': { data_type: 'float32', label: 'power' } },
} as ModbusLiveStreamRequest;

const cell = (rowIndex: number, key: string) => document.querySelector(`[data-cell="${rowIndex}:${key}"]`) as HTMLElement;
const grid = () => document.querySelector('[tabindex="0"]') as HTMLElement;

function editCell(rowIndex: number, key: string, value: string) {
  fireEvent.mouseDown(cell(rowIndex, key));
  fireEvent.mouseUp(window);
  fireEvent.keyDown(grid(), { key: 'F2' });
  const input = cell(rowIndex, key).querySelector('input')!;
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: 'Enter' });
}

function renderForm() {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ModbusStreamForm siteId={null} initialValues={request} initialAlias="" onSubmit={onSubmit} />
    </QueryClientProvider>,
  );
  return onSubmit;
}

describe('ModbusStreamForm register configs grid', () => {
  it('shows one row per address with the saved settings', () => {
    renderForm();
    expect(cell(0, 'address').textContent).toBe('0');
    expect(cell(1, 'label').textContent).toBe('power');
    expect(cell(1, 'data_type').textContent).toBe('float32');
    expect(cell(0, 'data_type').textContent).toBe('int16 (default)');
    expect(cell(3, 'address')).toBeNull();
  });

  it('has no delete column', () => {
    renderForm();
    expect(screen.queryByTitle('Delete row')).toBeNull();
    const headerCells = document.querySelector('thead tr')!.children;
    expect(headerCells).toHaveLength(1 + 5); // "#" + Address, Label, Data Type, Byte Order, Word Order
  });

  it('sends grid edits in the request', async () => {
    const onSubmit = renderForm();
    editCell(0, 'label', 'voltage');
    fireEvent.click(screen.getByRole('button', { name: 'Start Session' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const sent: ModbusLiveStreamRequest = onSubmit.mock.calls[0][0];
    expect(sent.register_configs).toEqual({
      '0': { data_type: 'int16', label: 'voltage' },
      '1': { data_type: 'float32', label: 'power' },
    });
  });

  it('marks an address outside start..end and does not submit', async () => {
    const onSubmit = renderForm();
    editCell(2, 'address', '99');
    fireEvent.click(screen.getByRole('button', { name: 'Start Session' }));

    await waitFor(() => expect(cell(2, 'address').className).toContain('bg-destructive/15'));
    expect(screen.getByText('Each register address must be within the start/end range')).toBeTruthy();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rebuilds rows when the range changes and keeps existing settings', async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText('End Address'), { target: { value: '3' } });

    await waitFor(() => expect(cell(3, 'address').textContent).toBe('3'));
    expect(cell(1, 'label').textContent).toBe('power');
  });
});
