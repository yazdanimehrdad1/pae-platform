// @vitest-environment jsdom
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { powerflowApi } from '@/api';
import type { EngineStatus, SetpointResult } from '@/api/types/powerflow';
import SimulationPage from '@/features/simulation/SimulationPage';
import { REFERENCE_SITE } from './fixtures';

const STATUS: EngineStatus = {
  state: 'running',
  test_mode: false,
  step_s: 1,
  step_id: 120,
  sim_time: '2026-06-21T06:02:00Z',
  last_converged: true,
  overrun_count: 0,
  nonconverged_count: 0,
  last_step_duration_ms: 12.5,
  history_count: 120,
  history_size: 3600,
};

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // Radix Select scrolls the chosen option into view
  // Radix Tabs/Select use pointer capture in jsdom
  Element.prototype.hasPointerCapture ??= () => false;
});

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(powerflowApi, 'listSites').mockResolvedValue({
    active: '2bess_1pv',
    stored_active: '2bess_1pv',
    sites: [
      { name: '1bess_1pv', category: 'default' },
      { name: '2bess_1pv', category: 'default' },
      { name: 'my_site', category: 'custom' },
    ],
  });
  vi.spyOn(powerflowApi, 'getStatus').mockResolvedValue(STATUS);
  vi.spyOn(powerflowApi, 'getSite').mockResolvedValue(REFERENCE_SITE);
  vi.spyOn(powerflowApi, 'listProfiles').mockResolvedValue({ load: ['high_demand'], pv: ['clear_sky_high'] });
  vi.spyOn(powerflowApi, 'getAssets').mockResolvedValue({
    bess: REFERENCE_SITE.bess ?? [],
    pv: REFERENCE_SITE.pv ?? [],
    loads: REFERENCE_SITE.loads ?? [],
    meters: REFERENCE_SITE.meters ?? [],
  });
  vi.spyOn(powerflowApi, 'getBess').mockResolvedValue({
    config: REFERENCE_SITE.bess![0],
    setpoint: { p_kw: 0, q_kvar: 0, mode: 'idle' },
    measurement: null,
  });
  vi.spyOn(powerflowApi, 'getPv').mockResolvedValue({
    config: REFERENCE_SITE.pv![0],
    setpoint: { p_limit_kw: 5000, p_limit_pct: 100, q_mode: 'q', q_kvar: 0, pf: 1 },
    measurement: null,
  });
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <SimulationPage />
    </QueryClientProvider>,
  );
}

// The element matching a selector, once it has rendered (waitFor retries until it exists).
const findElement = (selector: string) =>
  waitFor(() => {
    const element = document.querySelector(selector);
    if (!element) throw new Error(`${selector} not rendered yet`);
    return element as HTMLElement;
  });

const openTab = (name: string) => {
  const tab = screen.getByRole('tab', { name });
  fireEvent.mouseDown(tab);
  fireEvent.click(tab);
};

describe('SimulationPage', () => {
  it('shows the active site, its status and its single line diagram', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Simulation' })).toBeTruthy();
    await findElement('[data-simulation-sld]');
    expect(document.querySelector('[data-shape="bess:bess1"]')).not.toBeNull();
    expect(screen.getAllByText('running').length).toBeGreaterThan(0);
    expect(screen.getByText('120')).toBeTruthy(); // step id
  });

  it('stops before activating another site', async () => {
    const stop = vi.spyOn(powerflowApi, 'stop').mockResolvedValue({ ...STATUS, state: 'stopped' });
    const activate = vi.spyOn(powerflowApi, 'activateSite').mockResolvedValue(REFERENCE_SITE);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Sites');
    const row = await findElement('[data-site-row="1bess_1pv"]');
    fireEvent.click(within(row).getByRole('button', { name: 'Stop & activate' }));
    await waitFor(() => expect(activate).toHaveBeenCalledWith('1bess_1pv'));
    expect(stop).toHaveBeenCalled();
  });

  it("can't delete the active or a default site and confirms other deletes", async () => {
    const remove = vi.spyOn(powerflowApi, 'deleteSite').mockResolvedValue(undefined);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Sites');
    await screen.findByRole('button', { name: 'Delete my_site' });
    expect((screen.getByRole('button', { name: 'Delete 2bess_1pv' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Delete 1bess_1pv' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Delete my_site' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('my_site'));
  });

  it('has a Scenarios placeholder tab after Sites', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    const tabs = screen.getAllByRole('tab').map((tab) => tab.textContent);
    expect(tabs.slice(-2)).toEqual(['Sites', 'Scenarios']);
    openTab('Scenarios');
    expect(await screen.findByText(/Coming soon/)).toBeTruthy();
  });

  it('sends a BESS setpoint and shows that it was clamped', async () => {
    const result: SetpointResult = {
      asset_type: 'bess', asset_id: 'bess1', requested: { p_kw: 9000 },
      accepted: { p_kw: 2500, q_kvar: 0, mode: 'pq' }, clamped: true, flags: ['P_LIMIT'],
    };
    const setBess = vi.spyOn(powerflowApi, 'setBess').mockResolvedValue(result);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Assets & setpoints');
    const form = await findElement('[data-bess-form="bess1"]');
    fireEvent.change(within(form).getByLabelText('P kW (+ discharge)'), { target: { value: '9000' } });
    fireEvent.click(within(form).getByRole('button', { name: /Send/ }));
    await waitFor(() => expect(setBess).toHaveBeenCalledWith('bess1', { p_kw: 9000 }));
    expect(await within(form).findByText(/clamped: P_LIMIT/)).toBeTruthy();
  });
});
