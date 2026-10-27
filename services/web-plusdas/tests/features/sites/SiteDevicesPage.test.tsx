// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { devicesApi, sitesApi } from '@/api';
import type { Device } from '@/api/types/devices';
import type { Site } from '@/api/types/sites';
import SiteDevices from '@/features/sites/SiteDevicesPage';

const SITES = [
  { id: '1001', name: 'Alpha Solar Farm', location: 'San Diego, CA', type: 'facility', status: 'online' },
  { id: '1002', name: 'Beta Storage', location: 'Austin, TX', type: 'facility', status: 'online' },
] as Site[];

const DEVICE = {
  id: '10', name: 'bess-1', type: 'bess', status: 'online', location: 'yard', lastUpdate: 'now', points: ['1'],
  make: 'PAE', model: 'B1', serialNumber: '1', commStatus: 'connected', firmware: '1.0',
} as Device;

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname}{location.search}</p>;
}

function HistorianProbe() {
  const location = useLocation();
  return <p>historian for {(location.state as { selectedSite: Site }).selectedSite.name}</p>;
}

function renderPage(entry: string | { pathname: string; search?: string; state?: unknown }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/site-devices" element={<><SiteDevices /><LocationProbe /></>} />
          <Route path="/sites" element={<p>sites page</p>} />
          <Route path="/historian" element={<HistorianProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const heading = () => screen.findByRole('heading', { level: 1 });

beforeEach(() => {
  localStorage.clear();
  vi.spyOn(sitesApi, 'getAll').mockResolvedValue(SITES);
  vi.spyOn(devicesApi, 'getBySite').mockResolvedValue([DEVICE]);
});

describe('SiteDevices View Data', () => {
  it('is one button for the site, not one per device, and opens the Historian on that site', async () => {
    vi.spyOn(devicesApi, 'getBySite').mockResolvedValue([DEVICE, { ...DEVICE, id: '11', name: 'bess-2' }]);
    renderPage('/site-devices?siteId=1002');
    await screen.findByText('bess-2');
    const viewData = screen.getAllByRole('button', { name: 'View Data' });
    expect(viewData).toHaveLength(1);
    fireEvent.click(viewData[0]);
    expect(await screen.findByText('historian for Beta Storage')).toBeTruthy();
  });
});

describe('SiteDevices site', () => {
  it('opens the first site when reached from the navigation, and puts it in the URL', async () => {
    renderPage('/site-devices');
    expect((await heading()).textContent).toBe('Alpha Solar Farm Devices');
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/site-devices?siteId=1001'));
    expect(devicesApi.getBySite).toHaveBeenCalledWith('1001');
  });

  it('opens the site in ?siteId', async () => {
    renderPage('/site-devices?siteId=1002');
    expect((await heading()).textContent).toBe('Beta Storage Devices');
  });

  it('opens the site the link passed (Sites > Devices)', async () => {
    renderPage({ pathname: '/site-devices', state: { selectedSite: SITES[1] } });
    expect((await heading()).textContent).toBe('Beta Storage Devices');
  });

  it('reopens the last site viewed', async () => {
    localStorage.setItem('site_devices_last_site', '1002');
    renderPage('/site-devices');
    expect((await heading()).textContent).toBe('Beta Storage Devices');
  });

  it('goes to Sites when there are none', async () => {
    vi.spyOn(sitesApi, 'getAll').mockResolvedValue([]);
    renderPage('/site-devices');
    expect(await screen.findByText('sites page')).toBeTruthy();
  });
});
