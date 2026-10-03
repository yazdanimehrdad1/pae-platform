// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import type { ConditionPointOption } from '@/shared/components/conditions/conditionModel';
import { PointCombobox } from '@/shared/components/conditions/PointCombobox';

const option = (id: string, name: string, group: string): ConditionPointOption =>
  ({ id, name, label: `${group} · ${name}`, group, kind: 'numeric' });

const OPTIONS = [
  option('1', 'active_power', 'inverter'), option('2', 'reactive_power', 'inverter'),
  option('3', 'state_of_charge', 'battery'), option('4', 'pack_voltage', 'battery'),
];

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // cmdk scrolls the active option into view
});

function openPicker(value: string | null = null, options = OPTIONS) {
  const onChange = vi.fn();
  render(<PointCombobox options={options} value={value} onChange={onChange} ariaLabel="Point" />);
  fireEvent.click(screen.getByRole('combobox', { name: 'Point' }));
  return onChange;
}

const header = (group: string) => screen.getByRole('button', { name: new RegExp(`^${group}`) });
const optionNames = () => screen.queryAllByRole('option').map(item => item.textContent);

describe('PointCombobox', () => {
  it('lists every device collapsed, with its point count', () => {
    openPicker();
    expect(header('inverter').getAttribute('aria-expanded')).toBe('false');
    expect(within(header('battery')).getByText('2')).toBeTruthy();
    expect(optionNames()).toEqual([]);
    expect(screen.queryByText('No point found.')).toBeNull();
  });

  it('expands and collapses a device on click', () => {
    openPicker();
    fireEvent.click(header('battery'));
    expect(optionNames()).toEqual([expect.stringMatching(/^state_of_charge/), expect.stringMatching(/^pack_voltage/)]);
    fireEvent.click(header('battery'));
    expect(optionNames()).toEqual([]);
  });

  it('opens with the selected point\'s device expanded', () => {
    openPicker('3');
    expect(header('battery').getAttribute('aria-expanded')).toBe('true');
    expect(header('inverter').getAttribute('aria-expanded')).toBe('false');
  });

  it('opens a lone device expanded', () => {
    openPicker(null, OPTIONS.slice(0, 2));
    expect(optionNames()).toHaveLength(2);
  });

  it('searching shows matches across every device, collapsed or not', () => {
    openPicker();
    fireEvent.change(screen.getByPlaceholderText('Search devices and points'), { target: { value: 'power' } });
    expect(optionNames()).toEqual([expect.stringMatching(/^active_power/), expect.stringMatching(/^reactive_power/)]);
    fireEvent.change(screen.getByPlaceholderText('Search devices and points'), { target: { value: 'nothing-like-this' } });
    expect(screen.getByText('No point found.')).toBeTruthy();
  });

  it('selects a point from an expanded device', () => {
    const onChange = openPicker();
    fireEvent.click(header('inverter'));
    fireEvent.click(screen.getByRole('option', { name: /^reactive_power/ }));
    expect(onChange).toHaveBeenCalledWith('2');
  });
});
