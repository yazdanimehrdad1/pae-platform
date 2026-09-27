// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { createMockAlarmSource } from '@/mocks/alarms/mockAlarmSource';
import { ANCHOR } from '@/mocks/alarms/signals';
import { buildAlarmModel } from '../lib/alarmModel';
import { AlarmTable } from './AlarmTable';

async function renderTable(overrides: Partial<Parameters<typeof AlarmTable>[0]> = {}) {
  const snapshot = await createMockAlarmSource({ now: () => ANCHOR }).getSnapshot();
  const model = buildAlarmModel(snapshot);
  const props = {
    alarms: model.active,
    now: snapshot.now,
    timeZone: snapshot.site.timeZone,
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
  it('lists the active alarms faults first, then longest active', async () => {
    await renderTable();
    const rows = bodyRows();
    expect(rows.map(row => within(row).getAllByRole('cell')[2].textContent)).toEqual([
      'Protection P2', 'Site (calculated)', 'Transformer T1', 'Feeder F1',
    ]);
    expect(within(rows[0]).getByText('Fault')).toBeTruthy();
    expect(within(rows[0]).getByText('Phase B current > 600 A')).toBeTruthy();
    // The mock holds phase B at 688 A ± 4 A of noise.
    const p2Value = Number(within(rows[0]).getAllByRole('cell')[3].textContent!.match(/^(\d+) A/)![1]);
    expect(p2Value).toBeGreaterThanOrEqual(684);
    expect(p2Value).toBeLessThanOrEqual(692);
    expect(within(rows[0]).getAllByRole('cell')[3].textContent).toMatch(/ \/ > 600 A$/);
    expect(within(rows[0]).getByText('8 min')).toBeTruthy();
    expect(within(rows[1]).getByText('Warning')).toBeTruthy();
    expect(within(rows[2]).getByText('Top-oil temperature > 85 °C for 5 min')).toBeTruthy();
  });

  it("shows each rule's mobile and email channels and changes one without selecting the row", async () => {
    const { props, model } = await renderTable();
    const [p2Row, , t1Row, f1Row] = bodyRows();
    expect(screen.getAllByRole('columnheader').at(-1)!.textContent).toBe('Notifications');
    expect(screen.queryByRole('button', { name: /Ack/ })).toBeNull();

    const channels = (row: HTMLElement) => {
      const group = within(row).getByRole('group', { name: /^Notifications for / });
      return ['Mobile', 'Email'].map(name => within(group).getByRole('button', { name }).getAttribute('aria-pressed'));
    };
    expect(channels(p2Row)).toEqual(['true', 'true']); // seeded: both
    expect(channels(t1Row)).toEqual(['true', 'false']);
    expect(channels(f1Row)).toEqual(['false', 'false']);

    fireEvent.click(within(t1Row).getByRole('button', { name: 'Email' }));
    expect(props.onChangeNotify).toHaveBeenCalledWith(model.active[2].rule, { mobile: true, email: true });
    fireEvent.click(within(p2Row).getByRole('button', { name: 'Mobile' }));
    expect(props.onChangeNotify).toHaveBeenLastCalledWith(model.active[0].rule, { mobile: false, email: true });
    expect(props.onSelect).not.toHaveBeenCalled();
  });

  it('selects an alarm by click or keyboard', async () => {
    const { props, model } = await renderTable();
    fireEvent.click(bodyRows()[0]);
    expect(props.onSelect).toHaveBeenCalledWith(model.active[0]);
    fireEvent.keyDown(bodyRows()[1], { key: 'Enter' });
    expect(props.onSelect).toHaveBeenLastCalledWith(model.active[1]);
  });

  it('shows an empty state with the last cleared time and the cleared count', async () => {
    const { props } = await renderTable({ alarms: [] });
    expect(screen.getByText(/No active alarms · last cleared/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '2 cleared in last 6 h' }));
    expect(props.onOpenHistory).toHaveBeenCalled();
  });
});
