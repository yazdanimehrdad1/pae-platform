// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { buildAlarmModel } from '@/features/alarms/lib/alarmModel';
import { testSnapshot } from '@/features/alarms/lib/testData';
import { AlarmTable } from '@/features/alarms/components/AlarmTable';

function renderTable(overrides: Partial<Parameters<typeof AlarmTable>[0]> = {}) {
  const snapshot = testSnapshot();
  const model = buildAlarmModel(snapshot);
  const props = {
    alarms: model.active,
    model,
    now: snapshot.now,
    timeZone: 'UTC',
    selectedEventId: null,
    lastClearedAt: model.recentlyCleared[0]?.event.clearedAt ?? null,
    clearedCount: model.recentlyCleared.length,
    onSelect: vi.fn(),
    onChangeNotify: vi.fn(),
    onOpenHistory: vi.fn(),
    ...overrides,
  };
  render(<AlarmTable {...props} />);
  return { props, model };
}

const bodyRows = () => screen.getAllByRole('row').slice(1); // skip the header row

describe('AlarmTable', () => {
  it('lists active alarms with condition, device, value / limit and duration', () => {
    renderTable();
    const [row, profileRow] = bodyRows();
    expect(bodyRows()).toHaveLength(2);
    expect(within(profileRow).getAllByRole('cell')[1].textContent).toBe('PV inverter is not producing');
    const cells = within(row).getAllByRole('cell');
    expect(within(row).getByText('Fault')).toBeTruthy();
    expect(cells[1].textContent).toBe('bess-1 · state_of_charge < 20 % for 1 min');
    expect(cells[2].textContent).toBe('bess-1');
    expect(cells[3].textContent).toBe('15.50 % / < 20 %');
    expect(cells[4].textContent).toBe('8 min');
  });

  it("changes the rule's channels without selecting the row", () => {
    const { props, model } = renderTable();
    const group = within(bodyRows()[0]).getByRole('group', { name: 'Notifications for bess_soc_low' });
    fireEvent.click(within(group).getByRole('button', { name: 'Email' }));
    expect(props.onChangeNotify).toHaveBeenCalledWith(model.active[0].rule, { mobile: true, email: true });
    expect(props.onSelect).not.toHaveBeenCalled();
  });

  it('selects an alarm by click or keyboard', () => {
    const { props, model } = renderTable();
    fireEvent.click(bodyRows()[0]);
    expect(props.onSelect).toHaveBeenCalledWith(model.active[0]);
    fireEvent.keyDown(bodyRows()[0], { key: 'Enter' });
    expect(props.onSelect).toHaveBeenCalledTimes(2);
  });

  it('shows an empty state with the last cleared time, and the cleared count', () => {
    const { props } = renderTable({ alarms: [] });
    expect(screen.getByText(/No active alarms · last cleared/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '1 cleared in last 6 h' }));
    expect(props.onOpenHistory).toHaveBeenCalled();
  });
});
