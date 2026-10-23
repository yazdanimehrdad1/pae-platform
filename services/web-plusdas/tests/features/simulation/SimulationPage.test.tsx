// @vitest-environment jsdom
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { powerflowApi } from '@/api';
import type { AutoDispatchBess, AutoDispatchReport, BessBatteryState, ConditionsReport, DevicesSnapshot, EngineStatus, FaultCauseInfo, SetpointResult } from '@/api/types/powerflow';
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
  faults: [
    {
      asset_id: 'pv1',
      cause: 'ground_fault',
      severity: 'fault',
      latched: false,
      auto_restore: false,
      since_step: 90,
      restore_step: null,
      restore_sim_time: null,
    },
  ],
  comm_loss: [{ target: 'meter', id: 'm_bess2', since_step: 100 }],
  grid_vm_pu: null,
  grid_hz: null,
  scenario: null,
  scenarios: [],
};

const BATTERY: BessBatteryState = {
  asset_id: 'bess1',
  soc_pct: 62.5,
  round_trip_efficiency_pct: 100,
  eta_charge: 1,
  eta_discharge: 1,
};

const AUTO_DISPATCH_OFF: AutoDispatchReport = { enabled: false, power_pct: null, defaults: {}, bess_overrides: {}, bess: [] };

const dispatchedBess = (asset_id: string, overrides: Partial<AutoDispatchBess> = {}): AutoDispatchBess => ({
  asset_id,
  included: true,
  phase: 'discharging',
  direction: 'discharge',
  soc_pct: 62.5,
  soc_min_pct: 5,
  soc_max_pct: 95,
  soc_low_pct: 20,
  soc_high_pct: 80,
  discharge_pct: 50,
  charge_pct: 50,
  rest_s: 0,
  rest_remaining_s: null,
  p_noise_std_pct: 0,
  ramp_kw_per_s: null,
  q_kvar: 0,
  ...overrides,
});

// bess1 cycles (resting at an edge); bess2 is excluded and takes manual setpoints.
const AUTO_DISPATCH_ON: AutoDispatchReport = {
  enabled: true,
  power_pct: 50,
  defaults: { soc_low_pct: 20, soc_high_pct: 80 },
  bess_overrides: { bess2: { included: false } },
  bess: [
    dispatchedBess('bess1', { phase: 'resting', rest_remaining_s: 42 }),
    dispatchedBess('bess2', {
      included: false, phase: null, direction: null, soc_low_pct: null, soc_high_pct: null, discharge_pct: null,
      charge_pct: null, rest_s: null,
      p_noise_std_pct: null, q_kvar: null,
    }),
  ],
};

const cause = (asset_type: 'bess' | 'pv', cause: FaultCauseInfo['cause'], label: string, severity: 'fault' | 'warning'): FaultCauseInfo => ({
  asset_type,
  cause,
  label,
  severity,
  alrm: [],
  evt1: [],
  fault_code: 0,
  p_max_factor: 1,
  p_available_factor: 1,
});

const FAULT_CAUSES: FaultCauseInfo[] = [
  cause('bess', 'trip', 'Trip (generic)', 'fault'),
  cause('bess', 'fan_error', 'Fan error', 'warning'),
  cause('pv', 'trip', 'Trip (generic)', 'fault'),
  cause('pv', 'ground_fault', 'Ground fault', 'fault'),
];

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
  vi.spyOn(powerflowApi, 'getFaultCauses').mockResolvedValue(FAULT_CAUSES);
  vi.spyOn(powerflowApi, 'getAutoDispatch').mockResolvedValue(AUTO_DISPATCH_OFF);
  vi.spyOn(powerflowApi, 'listEventScenarios').mockResolvedValue([
    {
      name: 'trip',
      category: 'custom',
      description: 'Trip BESS 1',
      event_count: 2,
      expected_points: [],
      valid: true,
      problems: [],
    },
    {
      name: 'old',
      category: 'custom',
      description: null,
      event_count: 1,
      expected_points: [],
      valid: false,
      problems: ['event 1: no breaker'],
    },
  ]);
  vi.spyOn(powerflowApi, 'getSite').mockResolvedValue(REFERENCE_SITE);
  vi.spyOn(powerflowApi, 'listProfiles').mockResolvedValue({
    load: ['high_demand', 'low_demand'],
    pv: ['clear_sky_high', 'overcast_low'],
  });
  vi.spyOn(powerflowApi, 'getActiveConfig').mockResolvedValue(REFERENCE_SITE);
  vi.spyOn(powerflowApi, 'getProfileCsv').mockResolvedValue(['timestamp,p_kw,q_kvar', '2026-06-21T00:00:00Z,1,0', ''].join('\n'));
  vi.spyOn(powerflowApi, 'getAssets').mockResolvedValue({
    bess: REFERENCE_SITE.bess ?? [],
    pv: REFERENCE_SITE.pv ?? [],
    loads: REFERENCE_SITE.loads ?? [],
    meters: REFERENCE_SITE.meters ?? [],
  });
  vi.spyOn(powerflowApi, 'getBess').mockResolvedValue({
    config: REFERENCE_SITE.bess![0],
    setpoint: { p_kw: 0, q_kvar: 0, mode: 'idle' },
    battery: BATTERY,
    measurement: null,
  });
  vi.spyOn(powerflowApi, 'getPv').mockResolvedValue({
    config: REFERENCE_SITE.pv![0],
    setpoint: { p_limit_kw: 5000, p_limit_pct: 100, q_mode: 'q', q_kvar: 0, pf: 1 },
    measurement: null,
  });
});

function renderPage(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
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
    expect((await findElement('[data-fault="pv1:ground_fault"]')).textContent).toBe('Ground fault');
    const row = await findElement('[data-scenario-row="trip"]');
    fireEvent.click(within(row).getByRole('button', { name: 'Start trip' }));
    await waitFor(() => expect(start).toHaveBeenCalledWith('trip'));
    const stale = await findElement('[data-scenario-row="old"]');
    expect((within(stale).getByRole('button', { name: 'Start old' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows overlapping runs with their scenario step and schedules or stops one', async () => {
    const run = (name: string, state: 'scheduled' | 'playing', current_step: number | null, start_step: number) => ({
      name,
      started_step: start_step - 1,
      start_step,
      state,
      current_step,
      length: 700,
      total: 3,
      fired: state === 'playing' ? 1 : 0,
      missed: 0,
      next_step: 150,
      finished: false,
    });
    vi.spyOn(powerflowApi, 'getConditions').mockResolvedValue({
      ...CONDITIONS,
      scenarios: [run('trip', 'playing', 23, 98), run('sag', 'scheduled', null, 200)],
    });
    const start = vi.spyOn(powerflowApi, 'startEventScenario').mockResolvedValue(CONDITIONS);
    const stop = vi.spyOn(powerflowApi, 'stopEventScenario').mockResolvedValue(CONDITIONS);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Scenarios');
    const playing = await findElement('[data-scenario-status="trip"]');
    expect(playing.querySelector('[data-run-step]')?.textContent).toBe('scenario step 23 of 700');
    const scheduled = await findElement('[data-scenario-status="sag"]');
    expect(scheduled.querySelector('[data-run-step]')?.textContent).toBe('starts at sim step 200');
    // a playing scenario can't be started again, but others can
    const tripRow = await findElement('[data-scenario-row="trip"]');
    expect((within(tripRow).getByRole('button', { name: 'Start trip' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(scheduled).getByRole('button', { name: 'Stop sag' }));
    await waitFor(() => expect(stop).toHaveBeenCalledWith('sag'));
    const oldRow = await findElement('[data-scenario-row="old"]');
    expect((within(oldRow).getByRole('button', { name: 'Start old' }) as HTMLButtonElement).disabled).toBe(true); // stale
    expect(start).not.toHaveBeenCalled();
  });

  it('schedules a scenario at a sim step', async () => {
    const start = vi.spyOn(powerflowApi, 'startEventScenario').mockResolvedValue(CONDITIONS);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Scenarios');
    const row = await findElement('[data-scenario-row="trip"]');
    fireEvent.click(within(row).getByRole('button', { name: 'Schedule trip' }));
    const input = (await screen.findByLabelText('Start at sim step')) as HTMLInputElement;
    expect(input.value).toBe('130'); // the current step (120) + 10
    fireEvent.change(input, { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: 'Schedule' }));
    await waitFor(() => expect(start).toHaveBeenCalledWith('trip', 500));
  });

  it('injects a fault with auto-restore and resets a latched one', async () => {
    const apply = vi.spyOn(powerflowApi, 'applyCondition').mockResolvedValue(CONDITIONS);
    const reset = vi.spyOn(powerflowApi, 'resetAlarms').mockResolvedValue({} as SetpointResult);
    vi.spyOn(powerflowApi, 'getConditions').mockResolvedValue({
      ...CONDITIONS,
      faults: [{ ...CONDITIONS.faults[0], latched: true }],
    });
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Scenarios');
    const latched = await findElement('[data-fault="pv1:ground_fault"]');
    expect(latched.textContent).toBe('Ground fault · latched');
    const resetButton = screen.getByRole('button', { name: 'Reset alarms pv1' }) as HTMLButtonElement;
    await waitFor(() => expect(resetButton.disabled).toBe(false));
    fireEvent.click(resetButton);
    await waitFor(() => expect(reset).toHaveBeenCalledWith('pv', 'pv1'));
    fireEvent.click(screen.getByRole('switch', { name: 'Auto-restore bess1' }));
    fireEvent.click(screen.getByRole('button', { name: 'Inject fault bess1' }));
    await waitFor(() =>
      expect(apply).toHaveBeenCalledWith({ type: 'asset_fault', asset_id: 'bess1', active: true, cause: 'trip', auto_restore: true }),
    );
  });

  it('marks built-in scenarios and keeps them from being deleted', async () => {
    vi.spyOn(powerflowApi, 'listEventScenarios').mockResolvedValue([
      {
        name: 'poi-trip',
        category: 'default',
        description: 'POI opens at step 5',
        event_count: 2,
        expected_points: [
          { device: 'site.site', point: 'GridMode', equals: 'BLACKOUT', tolerance: 0, from_step: 5, to_step: 34 },
          { device: 'pv.pv1', point: 'Alrm', bits_set: ['GRID_DISCONNECT'], tolerance: 0, from_step: 5, to_step: null },
        ],
        valid: true,
        problems: [],
      },
    ]);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Scenarios');
    const row = await findElement('[data-scenario-row="poi-trip"]');
    expect(within(row).getByText('built-in')).toBeTruthy();
    expect((within(row).getByRole('button', { name: 'Delete poi-trip' }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(row).queryByRole('button', { name: 'Edit poi-trip' })).toBeNull(); // read-only
    vi.spyOn(powerflowApi, 'getEventScenario').mockResolvedValue({
      schema_version: 1,
      description: 'POI opens at step 5',
      events: [{ at: { kind: 'step', step: 5 }, change: { type: 'breaker', breaker: 'poi', closed: false }, label: null }],
      expected_points: [],
    });
    fireEvent.click(within(row).getByRole('button', { name: 'Duplicate poi-trip' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Duplicate poi-trip')).toBeTruthy();
    expect((within(dialog).getByLabelText('Name') as HTMLInputElement).value).toBe('poi-trip-copy');
    expect((within(dialog).getByLabelText('Name') as HTMLInputElement).disabled).toBe(false);
    expect(row.querySelector('[data-scenario-description]')?.textContent).toBe('POI opens at step 5');
    expect([...row.querySelectorAll('[data-scenario-points] li')].map((item) => item.textContent)).toEqual([
      'site.site GridMode = BLACKOUT · steps 5–34',
      'pv.pv1 Alrm has GRID_DISCONNECT · step 5',
    ]);
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

  it('turns auto dispatch on with per-BESS overrides and shows each BESS phase', async () => {
    const setAutoDispatch = vi.spyOn(powerflowApi, 'setAutoDispatch').mockResolvedValue(AUTO_DISPATCH_ON);
    // The refresh after the PUT reads it back on.
    vi.spyOn(powerflowApi, 'getAutoDispatch').mockImplementation(async () =>
      setAutoDispatch.mock.calls.length > 0 ? AUTO_DISPATCH_ON : AUTO_DISPATCH_OFF,
    );
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Scenarios');
    const toggle = await screen.findByRole('switch', { name: 'Auto dispatch' });
    expect(toggle.getAttribute('aria-checked')).toBe('false');
    fireEvent.change(screen.getByLabelText('Defaults SOC low %'), { target: { value: '20' } });
    fireEvent.change(screen.getByLabelText('Defaults Rest s'), { target: { value: '300' } });
    fireEvent.change(screen.getByLabelText('bess1 SOC high %'), { target: { value: '70' } });
    fireEvent.change(screen.getByLabelText('bess1 Discharge %'), { target: { value: '80' } });
    fireEvent.change(screen.getByLabelText('Defaults Charge %'), { target: { value: '30' } });
    fireEvent.click(screen.getByRole('switch', { name: 'Include bess2' }));
    expect((screen.getByLabelText('bess2 SOC low %') as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(toggle);
    await waitFor(() =>
      expect(setAutoDispatch).toHaveBeenCalledWith({
        enabled: true,
        power_pct: 50,
        defaults: { charge_pct: 30, soc_low_pct: 20, rest_s: 300 },
        bess: { bess1: { discharge_pct: 80, soc_high_pct: 70 }, bess2: { included: false } },
      }),
    );
    const row = await findElement('[data-auto-dispatch-bess="bess1"]');
    expect(await within(row).findByText('Resting')).toBeTruthy();
    expect(within(row).getByText(/42 s left/)).toBeTruthy();
    const excluded = await findElement('[data-auto-dispatch-bess="bess2"]');
    expect(within(excluded).getByText('manual setpoints')).toBeTruthy();
  });

  it('sets a BESS SOC and its round-trip efficiency from the Battery card', async () => {
    const setBattery = vi.spyOn(powerflowApi, 'setBessBattery').mockResolvedValue(BATTERY);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Scenarios');
    const row = await findElement('[data-battery-bess="bess1"]');
    expect(await within(row).findByText('62.5 %')).toBeTruthy();
    expect((within(row).getByLabelText('bess1 round-trip efficiency %') as HTMLInputElement).value).toBe('100');
    fireEvent.change(within(row).getByLabelText('bess1 set SOC %'), { target: { value: '10' } });
    fireEvent.click(within(row).getByRole('button', { name: 'Set' }));
    await waitFor(() => expect(setBattery).toHaveBeenCalledWith('bess1', { soc_pct: 10 }));
    fireEvent.change(within(row).getByLabelText('bess1 round-trip efficiency %'), { target: { value: '90' } });
    fireEvent.click(within(row).getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(setBattery).toHaveBeenCalledWith('bess1', { round_trip_efficiency_pct: 90 }));
    fireEvent.click(within(row).getByRole('button', { name: 'Use site config' }));
    await waitFor(() => expect(setBattery).toHaveBeenCalledWith('bess1', { round_trip_efficiency_pct: null }));
  });

  it('shows which profile each load and PV is simulating and which scenarios are in use', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Profiles');
    const selection = await findElement('[data-profile-selection]');
    expect(await within(selection).findByText('simulating: high_demand')).toBeTruthy();
    expect(within(selection).getByText('simulating: clear_sky_high')).toBeTruthy();
    expect(within(selection).getByRole('combobox', { name: 'Load Site load scenario' }).textContent).toContain('high_demand');
    const inUse = await findElement('[data-profile-scenario="load/high_demand"]');
    expect(within(inUse).getByText('in use: load1')).toBeTruthy();
    const unused = await findElement('[data-profile-scenario="load/low_demand"]');
    expect(within(unused).queryByText(/in use/)).toBeNull();
  });

  it('stops, saves the picked profile and starts again while the active site runs', async () => {
    const stop = vi.spyOn(powerflowApi, 'stop').mockResolvedValue({ ...STATUS, state: 'stopped' });
    const save = vi.spyOn(powerflowApi, 'saveSite').mockResolvedValue(REFERENCE_SITE);
    const start = vi.spyOn(powerflowApi, 'start').mockResolvedValue(STATUS);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Profiles');
    fireEvent.click(await findElement('[data-profile-scenario="load/low_demand"]'));
    fireEvent.click(await screen.findByRole('button', { name: 'Use for Site load' }));
    const selection = await findElement('[data-profile-selection]');
    expect(within(selection).getByRole('combobox', { name: 'Load Site load scenario' }).textContent).toContain('low_demand');
    fireEvent.click(within(selection).getByRole('button', { name: /Stop & save/ }));
    await waitFor(() => expect(start).toHaveBeenCalled());
    expect(stop).toHaveBeenCalled();
    const [name, config] = save.mock.calls[0];
    expect(name).toBe('2bess_1pv');
    expect(config.loads?.[0].profile).toEqual({ ...REFERENCE_SITE.loads![0].profile, scenario: 'low_demand' });
    expect(config.pv).toEqual(REFERENCE_SITE.pv);
    expect(stop.mock.invocationCallOrder[0]).toBeLessThan(save.mock.invocationCallOrder[0]);
    expect(save.mock.invocationCallOrder[0]).toBeLessThan(start.mock.invocationCallOrder[0]);
  });

  it('keeps an unsaved profile pick when the site is fetched again', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const getSite = vi.spyOn(powerflowApi, 'getSite').mockImplementation(async () => structuredClone(REFERENCE_SITE));
    renderPage(queryClient);
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Profiles');
    fireEvent.click(await findElement('[data-profile-scenario="pv/overcast_low"]'));
    fireEvent.click(await screen.findByRole('button', { name: 'Use for PV 1' }));
    const calls = getSite.mock.calls.length;
    await queryClient.invalidateQueries();
    await waitFor(() => expect(getSite.mock.calls.length).toBeGreaterThan(calls));
    const selection = await findElement('[data-profile-selection]');
    expect(within(selection).getByRole('combobox', { name: 'PV PV 1 (ac_kw) scenario' }).textContent).toContain('overcast_low');
    expect((within(selection).getByRole('button', { name: /Stop & save/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('keeps an unsaved Site settings edit when the site is fetched again', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const getSite = vi.spyOn(powerflowApi, 'getSite').mockImplementation(async () => structuredClone(REFERENCE_SITE));
    renderPage(queryClient);
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Site settings');
    fireEvent.change(await screen.findByLabelText('Load Site load scale'), { target: { value: '0.5' } });
    const calls = getSite.mock.calls.length;
    await queryClient.invalidateQueries();
    await waitFor(() => expect(getSite.mock.calls.length).toBeGreaterThan(calls));
    expect((screen.getByLabelText('Load Site load scale') as HTMLInputElement).value).toBe('0.5');
  });

  it('locks the setpoint form only of a BESS that auto dispatch drives', async () => {
    vi.spyOn(powerflowApi, 'getAutoDispatch').mockResolvedValue(AUTO_DISPATCH_ON);
    renderPage();
    await screen.findByRole('heading', { name: 'Simulation' });
    openTab('Assets & setpoints');
    const driven = await findElement('[data-bess-form="bess1"]');
    await within(driven).findByText(/Auto dispatch is on/);
    expect((within(driven).getByLabelText('P kW (+ discharge)') as HTMLInputElement).disabled).toBe(true);
    expect((within(driven).getByRole('button', { name: /Send/ }) as HTMLButtonElement).disabled).toBe(true);
    const excluded = await findElement('[data-bess-form="bess2"]');
    expect(within(excluded).queryByText(/Auto dispatch is on/)).toBeNull();
    expect((within(excluded).getByLabelText('P kW (+ discharge)') as HTMLInputElement).disabled).toBe(false);
  });
});
