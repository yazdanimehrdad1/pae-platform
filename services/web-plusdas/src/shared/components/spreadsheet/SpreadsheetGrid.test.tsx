// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { GridColumn, GridRow } from './grid';
import { SpreadsheetGrid } from './SpreadsheetGrid';

type Key = 'name' | 'order';

const COLUMNS: GridColumn<Key>[] = [
  { key: 'name', label: 'Name', kind: 'text', minWidth: 'min-w-[100px]' },
  { key: 'order', label: 'Order', kind: 'enum', options: ['big', 'little'], optional: true, minWidth: 'min-w-[100px]' },
];

const NEW_ROW: Record<Key, string> = { name: '', order: '' };

function makeRows(): GridRow<Key>[] {
  return [
    { key: 'a', values: { name: 'alpha', order: 'big' } },
    { key: 'b', values: { name: 'beta', order: '' } },
  ];
}

/** Holds the rows like a real parent and reports each change. */
function Harness({ onChange, readOnly = false, errorCells }: {
  onChange?: (rows: GridRow<Key>[]) => void;
  readOnly?: boolean;
  errorCells?: Set<string>;
}) {
  const [rows, setRows] = useState(makeRows);
  return (
    <SpreadsheetGrid
      columns={COLUMNS}
      rows={rows}
      onRowsChange={(next) => { setRows(next); onChange?.(next); }}
      newRowValues={NEW_ROW}
      readOnly={readOnly}
      errorCells={errorCells}
      onDeleteRow={(rowIndex) => setRows(previous => previous.filter((_, index) => index !== rowIndex))}
    />
  );
}

const cell = (rowIndex: number, key: Key) => document.querySelector(`[data-cell="${rowIndex}:${key}"]`) as HTMLElement;
const grid = () => document.querySelector('[tabindex="0"]') as HTMLElement;

function selectCell(rowIndex: number, key: Key) {
  fireEvent.mouseDown(cell(rowIndex, key));
  fireEvent.mouseUp(window);
}

function mockClipboard(readText = '') {
  const clipboard = { readText: vi.fn().mockResolvedValue(readText), writeText: vi.fn().mockResolvedValue(undefined) };
  Object.defineProperty(navigator, 'clipboard', { value: clipboard, configurable: true });
  return clipboard;
}

afterEach(() => vi.restoreAllMocks());

describe('SpreadsheetGrid', () => {
  it('renders the headers and every row', () => {
    render(<Harness />);
    expect(screen.getByText('Name')).toBeTruthy();
    expect(screen.getByText('Order')).toBeTruthy();
    expect(cell(0, 'name').textContent).toBe('alpha');
    expect(cell(1, 'order').textContent).toBe('—'); // empty optional enum
  });

  it('typing into a text cell and pressing Enter changes the row', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    selectCell(0, 'name');
    fireEvent.keyDown(grid(), { key: 'x' });
    const input = cell(0, 'name').querySelector('input')!;
    fireEvent.change(input, { target: { value: 'xray' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(cell(0, 'name').textContent).toBe('xray');
    expect(onChange.mock.lastCall![0][0].values.name).toBe('xray');
  });

  it('pastes TSV from the active cell, normalising enum casing and skipping values that do not fit', async () => {
    mockClipboard('gamma\tLITTLE\ndelta\tsideways');
    render(<Harness />);
    selectCell(0, 'name');
    fireEvent.keyDown(grid(), { key: 'v', ctrlKey: true });

    await waitFor(() => expect(cell(0, 'name').textContent).toBe('gamma'));
    expect(cell(0, 'order').textContent).toBe('little');
    expect(cell(1, 'name').textContent).toBe('delta');
    expect(cell(1, 'order').textContent).toBe('—'); // "sideways" isn't an option, cell unchanged
  });

  it('copies the selection as TSV', async () => {
    const clipboard = mockClipboard();
    render(<Harness />);
    fireEvent.mouseDown(cell(0, 'name'));
    fireEvent.mouseDown(cell(1, 'order'), { shiftKey: true });
    fireEvent.keyDown(grid(), { key: 'c', ctrlKey: true });

    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith('alpha\tbig\nbeta\t'));
  });

  it('adds rows with the new-row values', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /Add Row/ }));

    const rows = onChange.mock.lastCall![0];
    expect(rows).toHaveLength(3);
    expect(rows[2].values).toEqual(NEW_ROW);
  });

  it('narrows rows with the filter row', () => {
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Filter Name'), { target: { value: 'bet' } });
    expect(cell(0, 'name')).toBeNull();
    expect(cell(1, 'name').textContent).toBe('beta');
  });

  it('highlights error cells', () => {
    render(<Harness errorCells={new Set(['1:name'])} />);
    expect(cell(1, 'name').className).toContain('bg-destructive/15');
    expect(cell(0, 'name').className).not.toContain('bg-destructive/15');
  });

  it('read-only: no editing, pasting, adding or deleting, but copy still works', async () => {
    const clipboard = mockClipboard('changed');
    const onChange = vi.fn();
    render(<Harness onChange={onChange} readOnly />);
    selectCell(0, 'name');
    fireEvent.keyDown(grid(), { key: 'x' });
    fireEvent.keyDown(grid(), { key: 'Delete' });
    fireEvent.keyDown(grid(), { key: 'v', ctrlKey: true });
    fireEvent.keyDown(grid(), { key: 'c', ctrlKey: true });

    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith('alpha'));
    expect(cell(0, 'name').querySelector('input')).toBeNull();
    expect(cell(0, 'name').textContent).toBe('alpha');
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /Add Row/ })).toBeNull();
    expect(screen.queryByTitle('Delete row')).toBeNull();
  });
});
