// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { DevicePoint } from '@/api/types/devicePoints';
import { DevicePointsGrid } from '@/features/devices/DevicePointsGrid';

// Regression net for moving the grid onto the shared SpreadsheetGrid: saving, validation
// and the locked Category column must behave as before.
const point = {
  id: 7,
  site_id: 1001,
  device_id: 1,
  name: 'active_power',
  address: 100,
  size: 1,
  data_type: 'int16',
  scale_factor: 1,
  unit: 'W',
  byte_order: 'big',
  word_order: 'msw_first',
  poll_kind: 'holding',
  category: 'NATIVE',
  class: 'ANALOG',
  severity: null,
} as DevicePoint;

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

const enumPoint = {
  ...point, id: 8, name: 'InvSt', address: 101, data_type: 'enum16', unit: null, class: 'BINARY',
  enum_detail: { '3': 'RUNNING', '0': 'OFF' }, bitfield_detail: null,
} as DevicePoint;
const bitfieldPoint = {
  ...point, id: 9, name: 'Alrm', address: 102, data_type: 'bitfield32', size: 2, unit: null, class: 'ALARM',
  enum_detail: null, bitfield_detail: { '0': 'UNDERVOLTAGE', '3': 'GROUND_FAULT' },
} as DevicePoint;

function renderGrid(onSave = vi.fn().mockResolvedValue(undefined), onRequestDelete = vi.fn(), points = [point]) {
  render(<DevicePointsGrid points={points} disabled={false} isSaving={false} onSave={onSave} onRequestDelete={onRequestDelete} />);
  return onSave;
}

describe('DevicePointsGrid', () => {
  it('saves an edited point as an update', async () => {
    const onSave = renderGrid();
    editCell(0, 'unit', 'kW');

    const save = screen.getByRole('button', { name: /Save \(1\)/ });
    fireEvent.click(save);

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const changes = onSave.mock.calls[0][0];
    expect(changes.creates).toEqual([]);
    expect(changes.updates).toHaveLength(1);
    expect(changes.updates[0]).toMatchObject({ id: 7, payload: { name: 'active_power', unit: 'kW', class: 'ANALOG' } });
  });

  it('marks an invalid size and does not save', () => {
    const onSave = renderGrid();
    editCell(0, 'size', '0');
    fireEvent.click(screen.getByRole('button', { name: /Save \(1\)/ }));

    expect(cell(0, 'size').className).toContain('bg-destructive/15');
    expect(screen.getByText(/invalid cell highlighted/)).toBeTruthy();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('the trash button asks to delete the point', () => {
    const onRequestDelete = vi.fn();
    renderGrid(undefined, onRequestDelete);
    fireEvent.click(screen.getByTitle('Delete row'));
    expect(onRequestDelete).toHaveBeenCalledWith(point);
  });

  it('does not let an existing point change its category', () => {
    renderGrid();
    fireEvent.doubleClick(cell(0, 'category'));
    expect(cell(0, 'category').querySelector('select')).toBeNull();
    expect(cell(0, 'category').className).toContain('cursor-not-allowed');
  });

  it('shows enum and bitfield labels, in code order', () => {
    renderGrid(undefined, undefined, [point, enumPoint, bitfieldPoint]);
    expect(cell(0, 'labels').textContent).toBe('');
    expect(cell(1, 'labels').textContent).toBe('0=OFF; 3=RUNNING');
    expect(cell(2, 'labels').textContent).toBe('0=UNDERVOLTAGE; 3=GROUND_FAULT');
    // Only enum and bitfield points get the table editor.
    expect(screen.queryByRole('button', { name: 'Edit labels of active_power' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Edit labels of InvSt' })).toBeTruthy();
  });

  it('saves labels typed in the cell as the right detail', async () => {
    const onSave = renderGrid(undefined, undefined, [enumPoint, bitfieldPoint]);
    editCell(0, 'labels', '0=OFF; 3=RUNNING; 4=THROTTLED');
    editCell(1, 'labels', '5=COMM_LOSS');
    fireEvent.click(screen.getByRole('button', { name: /Save \(2\)/ }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [enumUpdate, bitUpdate] = onSave.mock.calls[0][0].updates;
    expect(enumUpdate.payload).toMatchObject({
      enum_detail: { '0': 'OFF', '3': 'RUNNING', '4': 'THROTTLED' }, bitfield_detail: null,
    });
    expect(bitUpdate.payload).toMatchObject({ enum_detail: null, bitfield_detail: { '5': 'COMM_LOSS' } });
  });

  it('rejects labels on a type that takes none, or a bit out of range', () => {
    const onSave = renderGrid(undefined, undefined, [point, bitfieldPoint]);
    editCell(0, 'labels', '1=ON');
    editCell(1, 'labels', '40=TOO_HIGH');
    fireEvent.click(screen.getByRole('button', { name: /Save \(2\)/ }));
    expect(cell(0, 'labels').className).toContain('bg-destructive/15');
    expect(cell(1, 'labels').className).toContain('bg-destructive/15');
    expect(onSave).not.toHaveBeenCalled();
  });

  it('edits labels in the table dialog, saved with the grid', async () => {
    const onSave = renderGrid(undefined, undefined, [enumPoint]);
    fireEvent.click(screen.getByRole('button', { name: 'Edit labels of InvSt' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Label 2'), { target: { value: 'ON' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Add code/ }));
    fireEvent.change(within(dialog).getByLabelText('Label 3'), { target: { value: 'FAULT' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply' }));
    expect(cell(0, 'labels').textContent).toBe('0=OFF; 3=ON; 4=FAULT');
    fireEvent.click(screen.getByRole('button', { name: /Save \(1\)/ }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave.mock.calls[0][0].updates[0].payload.enum_detail).toEqual({ '0': 'OFF', '3': 'ON', '4': 'FAULT' });
  });
});
