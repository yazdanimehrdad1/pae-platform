// @vitest-environment jsdom
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { powerflowApi } from '@/api';
import type { ConditionsReport, DevicesSnapshot, EngineStatus, SetpointResult } from '@/api/types/powerflow';
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
  scenario: null,
  speed: 1,
  start_time: '2026-06-21T00:00:00Z',
  start_step: 0,
  scheduled_start: null,
};

const DEVICES: DevicesSnapshot = {
  step_id: 120,
  sim_time: '2026-06-21T06:02:00Z',
  converged: true,
  devices: [
    {
      kind: 'bess', asset_id: 'bess1', base: 1000,
      points: [
        { point: 'W', label: 'Active Power', unit: 'W', data_type: 'int16', served: 'yes', value: 1_200_000, text: null },
        { point: 'InvSt', label: 'Inverter State', unit: '', data_type: 'enum16', served: 'calc', value: 3, text: 'RUNNING' },
        { point: 'TmpCab', label: 'Cabinet Temperature', unit: 'C', data_type: 'int16', served: 'no', value: null, text: null },
      ],
    },
    {
      kind: 'poi_meter', asset_id: 'meter', base: 4000,
      points: [{ point: 'W', label: 'Active Power', unit: 'W', data_type: 'int32', served: 'yes', value: -500_000, text: null }],
    },
  ],
};

const CONDITIONS: ConditionsReport = {
  breakers: [
    { id: 'poi', kind: 'poi', closed: true },
    { id: 'bess1', kind: 'bess', closed: false },
    { id: 'bess2', kind: 'bess', closed: true },
    { id: 'pv1', kind: 'pv', closed: true },
    { id: 'load1', kind: 'load', closed: true },
  ],
  faults: [{ asset_id: 'pv1', cause: 'ground_fault' }],
  comm_loss: [{ target: 'meter', id: 'm_bess2', since_step: 100 }],
  grid_vm_pu: null,
  grid_hz: null,
  scenario: null,
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
  vi.spyOn(powerflowApi, 'getConditions').mockResolvedValue(CONDITIONS);
  vi.spyOn(powerflowApi, 'listEventScenarios').mockResolvedValue([
    { name: 'trip', description: 'Trip BESS 1', event_count: 2, valid: true, problems: [] },
    { name: 'old', description: null, event_count: 1, valid: false, problems: ['event 1: no breaker'] },
  ]);
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

  it('has a Scenarios tab after Sites with live toggles and the stored scenarios', async () => {
    const apply = vi.spyOn(powerflowApi, 'applyCondition').mockResolvedValue(CONDITIONS);
    const start = vi.spyOn(powerflowApi, 'startEventScenario').mockResolvedValue(CONDITIONS);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    const tabs = screen.getAllByRole('tab').map((tab) => tab.textContent);
    expect(tabs.slice(-2)).toEqual(['Sites', 'Scenarios']);
    openTab('Scenarios');
    const breaker = await screen.findByRole('switch', { name: 'Breaker bess1 closed' });
    expect(breaker.getAttribute('aria-checked')).toBe('false');
    fireEvent.click(breaker);
    await waitFor(() =>
      expect(apply).toHaveBeenCalledWith({ type: 'breaker', breaker: 'bess1', closed: true }),
    );
    expect(screen.getByRole('switch', { name: 'Fault pv1' }).getAttribute('aria-checked')).toBe('true');
    const row = await findElement('[data-scenario-row="trip"]');
    fireEvent.click(within(row).getByRole('button', { name: 'Start' }));
    await waitFor(() => expect(start).toHaveBeenCalledWith('trip'));
    const stale = await findElement('[data-scenario-row="old"]');
    expect((within(stale).getByRole('button', { name: 'Start' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows live breakers on the SLD and switches one on click', async () => {
    const apply = vi.spyOn(powerflowApi, 'applyCondition').mockResolvedValue(CONDITIONS);
    renderPage();
    const open = await findElement('[data-shape="brk:bess1"][data-breaker="open"]');
    expect(await findElement('[data-shape="pv:pv1"][data-flags*="fault"]')).toBeTruthy();
    fireEvent.click(open);
    await waitFor(() =>
      expect(apply).toHaveBeenCalledWith({ type: 'breaker', breaker: 'bess1', closed: true }),
    );
  });

  it('sets the speed and schedules a start', async () => {
    const start = vi.spyOn(powerflowApi, 'start').mockResolvedValue(STATUS);
    vi.spyOn(powerflowApi, 'getStatus').mockResolvedValue({ ...STATUS, state: 'stopped' });
    renderPage();
    const input = await screen.findByLabelText('Start at');
    fireEvent.change(input, { target: { value: '2030-01-01T08:00:00' } });
    fireEvent.click(screen.getByRole('button', { name: /Schedule/ }));
    await waitFor(() => expect(start).toHaveBeenCalledWith(new Date('2030-01-01T08:00:00').toISOString()));
  });

  it('shows the standard device view and trends a point', async () => {
    vi.spyOn(powerflowApi, 'listDevices').mockResolvedValue(DEVICES);
    const history = vi.spyOn(powerflowApi, 'getDeviceHistory').mockResolvedValue({
      kind: 'bess', asset_id: 'bess1', base: 1000,
      points: [{ point: 'W', label: 'Active Power', unit: 'W' }],
      samples: [{ step_id: 120, sim_time: '2026-06-21T06:02:00Z', converged: true, values: [1_200_000] }],
    });
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Measurements');
    const power = await findElement('[data-point="W"] [data-value]');
    expect(power.textContent).toBe(`${(1_200_000).toLocaleString()} W`);
    expect((await findElement('[data-point="InvSt"] [data-value]')).textContent).toBe('RUNNING (3)');
    expect(document.querySelector('[data-point="TmpCab"]')).toBeNull(); // unserved hidden by default
    fireEvent.click(screen.getByRole('checkbox', { name: 'Trend W' }));
    await waitFor(() => expect(history).toHaveBeenCalledWith('bess', 'bess1', ['W']));
    fireEvent.click(await findElement('[data-device="poi_meter.meter"]'));
    expect((await findElement('[data-point="W"] [data-value]')).textContent).toBe(`${(-500_000).toLocaleString()} W`);
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
