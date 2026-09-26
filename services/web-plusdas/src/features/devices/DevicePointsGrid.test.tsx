// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { DevicePoint } from '@/shared/types/device-point';
import { DevicePointsGrid } from './DevicePointsGrid';

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

function renderGrid(onSave = vi.fn().mockResolvedValue(undefined), onRequestDelete = vi.fn()) {
  render(<DevicePointsGrid points={[point]} disabled={false} isSaving={false} onSave={onSave} onRequestDelete={onRequestDelete} />);
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
});
