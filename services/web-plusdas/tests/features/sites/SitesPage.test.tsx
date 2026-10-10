// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { sitesApi } from '@/api';
import type { Site, SiteHealth } from '@/api/types/sites';
import Sites from '@/features/sites/SitesPage';
import { SITE_STATS_REFRESH_MS } from '@/features/sites/hooks/useSiteHealth';

const SITES = [
  { id: '1001', name: 'Alpha Solar Farm', location: 'San Diego, CA', type: 'facility', status: 'online', deviceCount: 2,
    lastUpdate: '2026-10-09T12:00:00Z', operator: 'Alpha Ops', description: '' },
] as Site[];

const HEALTH: SiteHealth = {
  site_id: 1001,
  generated_at: '2026-10-09T12:00:00Z',
  highest_severity: 'HIGH',
  high_count: 3,
  medium_count: 6,
  low_count: 7,
  unknown_count: 1,
  devices: [
    {
      device_id: 12,
      device_name: 'meter-1',
      highest_severity: 'HIGH',
      high_count: 1,
      medium_count: 1,
      low_count: 0,
      unknown_count: 1,
      active_alarms: [
        { device_point_id: 301, device_point_name: 'trip', severity: 'HIGH', value: 1, active_bits: [], timestamp: '2026-10-09T12:00:00Z' },
        { device_point_id: 303, device_point_name: 'bms_alarms', severity: 'MEDIUM', value: 2, active_bits: ['OVER_VOLT'], timestamp: '2026-10-09T12:00:00Z' },
      ],
    },
    { device_id: 13, device_name: 'meter-2', highest_severity: null, high_count: 0, medium_count: 0, low_count: 0, unknown_count: 0, active_alarms: [] },
  ],
};

function DevicesPageProbe() {
  const location = useLocation();
  return <p>devices page for {(location.state as { selectedSite: Site }).selectedSite.name}</p>;
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/sites']}>
        <Routes>
          <Route path="/sites" element={<Sites />} />
          <Route path="/site-devices" element={<DevicesPageProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const siteBar = () => screen.findByRole('button', { name: 'Expand Alpha Solar Farm' });

async function severityCounts() {
  const counts = within(await screen.findByLabelText('Active alarms by severity'));
  return ['High', 'Medium', 'Low'].map((label) => counts.getByText(label).previousElementSibling?.textContent);
}

beforeEach(() => {
  vi.spyOn(sitesApi, 'getAll').mockResolvedValue(SITES);
  vi.spyOn(sitesApi, 'getHealth').mockResolvedValue(HEALTH);
});

describe('Sites page', () => {
  it('no longer shows the site stats cards', async () => {
    renderPage();
    await siteBar();
    expect(screen.queryByText('Total Sites')).toBeNull();
    expect(screen.queryByText('Offline')).toBeNull();
  });

  it('shows the severity counts on a collapsed bar, and the alarms per device only when expanded', async () => {
    renderPage();
    const bar = await siteBar();

    expect(await severityCounts()).toEqual(['3', '6', '7']);
    expect(sitesApi.getHealth).toHaveBeenCalledWith('1001');
    expect(screen.queryByText('trip')).toBeNull();

    fireEvent.click(bar);

    expect(await screen.findByText('trip')).toBeTruthy();
    expect(bar.getAttribute('aria-expanded')).toBe('true');
    expect(await severityCounts()).toEqual(['3', '6', '7']); // still on the bar when open
    expect(screen.getByText('bms_alarms')).toBeTruthy();
    expect(screen.getByText('OVER_VOLT')).toBeTruthy();
    expect(screen.getAllByText('High').length).toBeGreaterThan(1); // the bar count and the trip row
    expect(screen.getByText('meter-2')).toBeTruthy();
    expect(screen.getByText('No active alarms')).toBeTruthy();
    expect(screen.getAllByText('1 point never reported').length).toBe(2); // the site and meter-1
  });

  it('collapses again on a second click and toggles from the keyboard', async () => {
    renderPage();
    const bar = await siteBar();

    fireEvent.keyDown(bar, { key: 'Enter' });
    expect(await screen.findByText('trip')).toBeTruthy();

    fireEvent.click(bar);
    expect(bar.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('trip')).toBeNull();
  });

  it('shows the error when the health request fails', async () => {
    vi.spyOn(sitesApi, 'getHealth').mockRejectedValue({ detail: { error: 'NotFoundError', message: 'Site with id 1001 not found' } });
    renderPage();
    expect(await screen.findByText('Alarms unavailable')).toBeTruthy();
    fireEvent.click(await siteBar());
    expect(await screen.findByText('Site with id 1001 not found')).toBeTruthy();
  });

  it('opens the devices page from the Devices button without expanding the bar', async () => {
    renderPage();
    await siteBar();

    fireEvent.click(screen.getByRole('button', { name: 'Devices' }));

    expect(await screen.findByText('devices page for Alpha Solar Farm')).toBeTruthy();
    expect(screen.queryByText('trip')).toBeNull();
  });
});

describe('Sites page refresh', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

  it('refetches the sites list and each site health every 4 minutes, and shows the new counts', async () => {
    renderPage();
    expect(await severityCounts()).toEqual(['3', '6', '7']);
    expect(sitesApi.getAll).toHaveBeenCalledTimes(1);
    expect(sitesApi.getHealth).toHaveBeenCalledTimes(1);

    vi.spyOn(sitesApi, 'getHealth').mockResolvedValue({ ...HEALTH, high_count: 0, medium_count: 1, low_count: 2 });
    await advance(SITE_STATS_REFRESH_MS);

    await waitFor(() => expect(sitesApi.getAll).toHaveBeenCalledTimes(2));
    expect(sitesApi.getHealth).toHaveBeenCalledTimes(1); // the new spy: one refetch
    expect(sitesApi.getHealth).toHaveBeenCalledWith('1001');
    await waitFor(async () => expect(await severityCounts()).toEqual(['0', '1', '2']));
  });

  it('does not refetch before 4 minutes', async () => {
    renderPage();
    await severityCounts();

    await advance(SITE_STATS_REFRESH_MS - 1000);

    expect(sitesApi.getAll).toHaveBeenCalledTimes(1);
    expect(sitesApi.getHealth).toHaveBeenCalledTimes(1);
  });
});
