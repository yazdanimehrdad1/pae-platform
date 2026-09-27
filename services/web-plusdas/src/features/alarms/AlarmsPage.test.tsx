// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AlarmsPage from './AlarmsPage';

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AlarmsPage />
    </QueryClientProvider>,
  );
}

const alarmRow = (source: string) =>
  within(screen.getByRole('region', { name: 'Active alarms' })).getByRole('cell', { name: source }).closest('tr')!;
const deviceHeading = () => screen.getByRole('heading', { level: 2, name: /^(Transformer|Generator|Feeder|Protection|Switch)/ });

describe('AlarmsPage', () => {
  it('summarizes the site and opens on the worst device', async () => {
    renderPage();
    expect(await screen.findByText('1 active fault')).toBeTruthy();
    expect(screen.getByText('3 active warnings')).toBeTruthy();
    expect(screen.getByText('5 of 8 devices normal')).toBeTruthy();
    expect(deviceHeading().textContent).toBe('Protection P2');
  });

  it('opens the alarm device with the offending point in the trend when an alarm row is clicked', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    fireEvent.click(alarmRow('Transformer T1'));

    expect(deviceHeading().textContent).toBe('Transformer T1');
    expect(screen.getByRole('heading', { level: 3, name: /^Top-oil temperature/ })).toBeTruthy();
    expect(screen.getByText('Modbus TCP · 10.0.4.11 · unit 1')).toBeTruthy();
  });

  it('keeps the current device when a calculated (site) alarm is clicked', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    fireEvent.click(alarmRow('Feeder F1'));
    fireEvent.click(alarmRow('Site (calculated)'));

    expect(deviceHeading().textContent).toBe('Feeder F1');
    expect(alarmRow('Site (calculated)').getAttribute('aria-selected')).toBe('true');
  });

  it('saves notification channels to the rule, so the rules dialog shows them too', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    const tableEmail = () => within(alarmRow('Transformer T1')).getByRole('button', { name: 'Email' });
    expect(tableEmail().getAttribute('aria-pressed')).toBe('false');

    fireEvent.click(tableEmail());

    await waitFor(() => expect(tableEmail().getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(screen.getByRole('button', { name: /^Rules \(/ }));
    const dialog = await screen.findByRole('dialog');
    const group = within(dialog).getByRole('group', { name: 'Notifications for t1_top_oil_temp_high' });
    expect(within(group).getByRole('button', { name: 'Mobile' }).getAttribute('aria-pressed')).toBe('true');
    expect(within(group).getByRole('button', { name: 'Email' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('turns off every notification from the rules dialog after confirming', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    fireEvent.click(screen.getByRole('button', { name: /^Rules \(/ }));
    const dialog = await screen.findByRole('dialog');
    const turnOffAll = within(dialog).getByRole('button', { name: 'Turn off all notifications' });

    fireEvent.click(turnOffAll);
    const confirm = await screen.findByRole('alertdialog');
    expect(within(confirm).getByText(/turned off for \d+ rules/)).toBeTruthy();
    fireEvent.click(within(confirm).getByRole('button', { name: 'Turn off' }));

    await waitFor(() => expect(turnOffAll.hasAttribute('disabled')).toBe(true));
    const pressed = within(dialog).getAllByRole('button', { name: /^(Mobile|Email)$/ }).map(toggle => toggle.getAttribute('aria-pressed'));
    expect(pressed.length).toBeGreaterThan(0);
    expect(pressed.every(value => value === 'false')).toBe(true);
    expect(within(dialog).getByText(/0 of \d+ rules send notifications/)).toBeTruthy();
  });

  it('keeps notifications when the confirmation is cancelled', async () => {
    renderPage();
    await screen.findByText('1 active fault');
    fireEvent.click(within(alarmRow('Transformer T1')).getByRole('button', { name: 'Mobile' }));
    await waitFor(() => expect(within(alarmRow('Transformer T1')).getByRole('button', { name: 'Mobile' })
      .getAttribute('aria-pressed')).toBe('true'));
    fireEvent.click(screen.getByRole('button', { name: /^Rules \(/ }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Turn off all notifications' }));
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Cancel' }));

    expect(within(dialog).getByText(/1 of \d+ rules send notifications/)).toBeTruthy();
  });
});
