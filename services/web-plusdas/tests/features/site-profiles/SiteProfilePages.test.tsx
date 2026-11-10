// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { authApi, siteProfilesApi, sitesApi } from '@/api';
import type { MeResponse } from '@/api/types/me';
import type { PendingChanges, ProfileVersion, SiteProfileStatus } from '@/api/types/siteProfiles';
import { AuthProvider } from '@/shared/contexts/auth';
import SiteProfilesPage from '@/features/site-profiles/SiteProfilesPage';
import SiteProfileDetailPage from '@/features/site-profiles/SiteProfileDetailPage';

const ADMIN: MeResponse = { id: 1, email: 'root@example.com', display_name: 'Root', role: 'admin' };
const FETCHED_AT = '2026-11-07T10:00:00Z';
const NEW_SITE: SiteProfileStatus = { site_id: 1001, name: 'Powerflow 2BESS 1PV', approved_version: null, pending_changes: 3, fetched_at: FETCHED_AT };
const PENDING: PendingChanges = {
  site_id: 1001,
  fetched_at: FETCHED_AT,
  approved_version: null,
  changes: [
    { change_id: 'site', target: 'site', kind: 'added', summary: "site 'Powerflow 2BESS 1PV'", fields: [] },
    { change_id: 'device:12', target: 'device', kind: 'added', summary: "new INVERTER 'pv1' with 40 points", fields: [], device_id: 12 },
    { change_id: 'topology', target: 'topology', kind: 'added', summary: 'topology: 9 nodes, 8 connections', fields: [] },
  ],
};
const VERSION_1: ProfileVersion = {
  site_id: 1001, version: 1, approved_at: '2026-11-07T10:05:00Z', approved_by: 'root@example.com', change_ids: ['site', 'device:12'],
  catalog: {
    site: { site_id: 1001, name: 'Powerflow 2BESS 1PV', timezone: 'America/Phoenix' },
    devices: [{ device_id: 12, name: 'pv1', type: 'INVERTER' }],
    points: [{ name: 'pv1.active_power', device_id: 12, device_name: 'pv1', equipment: 'inverter', data_type: 'float32', unit: 'kW', description: 'AC output power' }],
    topology: { nodes: [], connections: [] },
    functions: [
      { name: 'site-bess1-round-trip-efficiency', kind: 'site', summary: "BESS 1's round trip efficiency (%)", output: 'scalar', device_types: [], parameters: [] },
      {
        name: 'device-inverter-availability', kind: 'device', summary: 'Inverter availability (%)', output: 'scalar', device_types: ['INVERTER'],
        parameters: [{ name: 'lookback_days', type: 'integer', default: 7, required: false }],
      },
      { name: 'site-assets-active-power', kind: 'site', summary: 'Assets active power (kW)', output: 'series', device_types: [], parameters: [] },
    ],
  },
};

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});
afterEach(() => vi.restoreAllMocks());

function renderAt(path: string, me: MeResponse = ADMIN) {
  vi.spyOn(authApi, 'me').mockResolvedValue(me);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/site-profiles" element={<SiteProfilesPage />} />
            <Route path="/site-profiles/:siteId" element={<SiteProfileDetailPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const notFound = { status: 404, detail: 'site not onboarded: no approved profile' };

describe('SiteProfilesPage', () => {
  it("lists the sites with the AI's access and the changes waiting", async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([NEW_SITE, { ...NEW_SITE, site_id: 7, name: 'Mesa', approved_version: 2, pending_changes: 0 }]);
    renderAt('/site-profiles');
    const newRow = (await screen.findByText('Powerflow 2BESS 1PV')).closest('tr') as HTMLElement;
    expect(within(newRow).getByText('Not onboarded')).toBeTruthy();
    expect(within(newRow).getByText('3 to review')).toBeTruthy();
    const mesaRow = screen.getByText('Mesa').closest('tr') as HTMLElement;
    expect(within(mesaRow).getByText('Onboarded · v2')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open the knowledge base of Mesa' }).getAttribute('href')).toBe('/site-profiles/7?tab=knowledge');
  });

  it("the site's button opens its page on the Knowledge tab", async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([NEW_SITE]);
    vi.spyOn(siteProfilesApi, 'get').mockRejectedValue(notFound);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue(PENDING);
    renderAt('/site-profiles');
    fireEvent.click(await screen.findByRole('link', { name: 'Open the knowledge base of Powerflow 2BESS 1PV' }));
    expect(await screen.findByRole('tab', { name: 'Knowledge', selected: true })).toBeTruthy();
    expect(await screen.findByText(/Onboard the site first/)).toBeTruthy();
  });

  it('tells a non-admin it is for administrators, and loads nothing', async () => {
    const list = vi.spyOn(siteProfilesApi, 'list');
    renderAt('/site-profiles', { ...ADMIN, role: 'engineer' });
    expect(await screen.findByText(/Only administrators/)).toBeTruthy();
    expect(list).not.toHaveBeenCalled();
  });
});

describe('SiteProfileDetailPage', () => {
  it('onboards a new site: the first approval needs the site, and sends the reviewed read', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([NEW_SITE]);
    vi.spyOn(siteProfilesApi, 'get').mockRejectedValue(notFound);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue(PENDING);
    const approve = vi.spyOn(siteProfilesApi, 'approve').mockResolvedValue(VERSION_1);
    renderAt('/site-profiles/1001');

    expect(await screen.findByText(/Not onboarded: the AI doesn't see this site yet/)).toBeTruthy();
    fireEvent.click(await screen.findByRole('checkbox', { name: /new INVERTER 'pv1'/ }));
    expect(screen.getByText("A new site's first approval must include the site itself.")).toBeTruthy();
    expect((screen.getByRole('button', { name: /Approve selected/ }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole('checkbox', { name: /site 'Powerflow 2BESS 1PV'/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Approve selected (2)' }));
    await waitFor(() => expect(approve).toHaveBeenCalledWith(1001, { change_ids: ['device:12', 'site'], fetched_at: FETCHED_AT }));
  });

  it('offers to read backend-ot when the site was never read', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([]);
    vi.spyOn(siteProfilesApi, 'get').mockRejectedValue(notFound);
    vi.spyOn(siteProfilesApi, 'changes').mockRejectedValue({ status: 404, detail: 'site not synced from backend-ot yet' });
    const sync = vi.spyOn(siteProfilesApi, 'sync').mockResolvedValue(PENDING);
    renderAt('/site-profiles/1001');
    expect(await screen.findByText(/hasn't been read from backend-ot yet/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Read backend-ot now/ }));
    await waitFor(() => expect(sync).toHaveBeenCalledWith(1001));
  });

  it('shows what the AI knows: the approved devices and their points', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([{ ...NEW_SITE, approved_version: 1, pending_changes: 0 }]);
    vi.spyOn(siteProfilesApi, 'get').mockResolvedValue(VERSION_1);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({ ...PENDING, approved_version: 1, changes: [] });
    renderAt('/site-profiles/1001');
    expect(await screen.findByText('The AI uses profile version 1.')).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'What the AI knows' }));
    fireEvent.click(await screen.findByRole('button', { name: /pv1/ }));
    expect(await screen.findByText('AC output power')).toBeTruthy();
  });

  it('lists site function changes in their own group', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([{ ...NEW_SITE, approved_version: 1, pending_changes: 1 }]);
    vi.spyOn(siteProfilesApi, 'get').mockResolvedValue(VERSION_1);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({
      ...PENDING,
      approved_version: 1,
      changes: [{
        change_id: 'function:site-poi-active-power', target: 'function', kind: 'added', fields: [],
        function_name: 'site-poi-active-power', summary: 'new site function site-poi-active-power: POI power',
      }],
    });
    renderAt('/site-profiles/1001');
    expect(await screen.findByText('Site functions')).toBeTruthy();
    expect(screen.getByText('new site function site-poi-active-power: POI power')).toBeTruthy();
  });

  it('lists the approved site functions and test-runs one as the AI would', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([{ ...NEW_SITE, approved_version: 1, pending_changes: 0 }]);
    vi.spyOn(siteProfilesApi, 'get').mockResolvedValue(VERSION_1);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({ ...PENDING, approved_version: 1, changes: [] });
    const testRun = vi.spyOn(siteProfilesApi, 'testRunFunction').mockResolvedValue({
      function: 'device-inverter-availability', start: '2026-11-07T09:00:00Z', end: '2026-11-08T09:00:00Z', device_id: 12,
      result: { availability_pct: 97.5 },
      backend_ot_result: { availability_pct: 97.5 },
    });
    renderAt('/site-profiles/1001');
    expect(await screen.findByText('The AI uses profile version 1.')).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'What the AI knows' }));
    expect(await screen.findByText("BESS 1's round trip efficiency (%)")).toBeTruthy();
    expect(screen.getByText('Each INVERTER')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Try device-inverter-availability' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Window'), { target: { value: '168' } });
    fireEvent.change(within(dialog).getByLabelText('lookback_days'), { target: { value: '3' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Run' }));

    expect(await within(dialog).findByText(/"availability_pct": 97.5/)).toBeTruthy();
    const [siteId, name, body] = testRun.mock.calls[0];
    expect([siteId, name, body.device_id, body.parameters]).toEqual([1001, 'device-inverter-availability', 12, { lookback_days: 3 }]);
    expect(new Date(body.end).getTime() - new Date(body.start).getTime()).toBe(168 * 3_600_000);
  });

  it("shows the test-run's times in the site's time zone, and the raw UTC result on request", async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([{ ...NEW_SITE, approved_version: 1, pending_changes: 0 }]);
    vi.spyOn(siteProfilesApi, 'get').mockResolvedValue(VERSION_1);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({ ...PENDING, approved_version: 1, changes: [] });
    vi.spyOn(sitesApi, 'getAll').mockResolvedValue([{
      id: '1001', name: 'Powerflow 2BESS 1PV', location: '', type: 'facility', status: 'online', deviceCount: 9,
      lastUpdate: FETCHED_AT, operator: 'x', description: '', timezone: 'America/Los_Angeles',
    }]);
    vi.spyOn(siteProfilesApi, 'testRunFunction').mockResolvedValue({
      function: 'site-bess1-round-trip-efficiency', start: '2026-11-08T22:21:06Z', end: '2026-11-09T22:21:06Z', device_id: null,
      result: { end_time: '2026-11-09T22:21:06.211000Z', efficiency_pct: 88.5 },
      backend_ot_result: { end_time: '2026-11-09T22:21:06.211000Z', efficiency_pct: 88.5 },
    });
    renderAt('/site-profiles/1001');
    expect(await screen.findByText(/Times in America\/Los_Angeles/)).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'What the AI knows' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Try site-bess1-round-trip-efficiency' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Run' }));

    // 22:21 UTC is 14:21 in Los Angeles (UTC-8 in November).
    expect(await within(dialog).findByText(/08 Nov, 14:21 .* → 09 Nov, 14:21/)).toBeTruthy();
    const result = within(dialog).getByLabelText('Result');
    expect(result.textContent).toMatch(/"end_time": "09 Nov, 14:21 [^"]+"/);
    fireEvent.click(within(dialog).getByRole('switch', { name: 'Show the raw result' }));
    expect(result.textContent).toContain('"end_time": "2026-11-09T22:21:06.211000Z"');
  });

  it('offers a series function at most 6 hours, as 15-minute buckets or every reading', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([{ ...NEW_SITE, approved_version: 1, pending_changes: 0 }]);
    vi.spyOn(siteProfilesApi, 'get').mockResolvedValue(VERSION_1);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({ ...PENDING, approved_version: 1, changes: [] });
    const testRun = vi.spyOn(siteProfilesApi, 'testRunFunction').mockResolvedValue({
      function: 'site-assets-active-power', start: '2026-11-09T16:00:00Z', end: '2026-11-09T22:00:00Z', device_id: null,
      result: {
        series: {
          resolution: 'first reading every 15 min',
          timeseries: [{ time: '2026-11-09T16:00:05Z', value: 10 }, { time: '2026-11-09T16:15:05Z', value: 30 }],
          gaps: [], coverage_percent: 100,
        },
      },
      backend_ot_result: {
        series: {
          timeseries: [
            { time: '2026-11-09T16:00:05Z', value: 10 }, { time: '2026-11-09T16:07:05Z', value: 20 },
            { time: '2026-11-09T16:15:05Z', value: 30 },
          ],
        },
      },
    });
    renderAt('/site-profiles/1001');
    fireEvent.mouseDown(await screen.findByRole('tab', { name: 'What the AI knows' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Try site-assets-active-power' }));
    const dialog = await screen.findByRole('dialog');
    const windows = within(dialog).getByLabelText('Window') as HTMLSelectElement;
    expect([...windows.options].map(option => option.text)).toEqual(['Last 15 minutes', 'Last hour', 'Last 6 hours']);
    expect(windows.value).toBe('6');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Run' }));
    expect(await within(dialog).findByText(/"resolution": "first reading every 15 min"/)).toBeTruthy();
    // The page checks the AI's rows against backend-ot's untouched result, which it can also show.
    expect(within(dialog).getByText(/✓ 2 of 2 rows are backend-ot's first reading of each 15 min \(from 3 readings\)/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('switch', { name: "Show backend-ot's original" }));
    expect(within(dialog).getByLabelText('Result', { selector: 'pre' }).textContent).toContain('"value": 20');
    fireEvent.click(within(dialog).getByRole('switch', { name: 'Every reading' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Run' }));
    await waitFor(() => expect(testRun).toHaveBeenCalledTimes(2));

    const [first, second] = testRun.mock.calls.map(call => call[2]);
    expect([first.resolution, second.resolution]).toEqual(['15min', 'raw']);
    expect(new Date(first.end).getTime() - new Date(first.start).getTime()).toBe(6 * 3_600_000);
  });

  it('offers no resolution for a scalar function', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([{ ...NEW_SITE, approved_version: 1, pending_changes: 0 }]);
    vi.spyOn(siteProfilesApi, 'get').mockResolvedValue(VERSION_1);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({ ...PENDING, approved_version: 1, changes: [] });
    renderAt('/site-profiles/1001');
    fireEvent.mouseDown(await screen.findByRole('tab', { name: 'What the AI knows' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Try site-bess1-round-trip-efficiency' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).queryByRole('switch', { name: 'Every reading' })).toBeNull();
    expect((within(dialog).getByLabelText('Window') as HTMLSelectElement).value).toBe('24');
  });

  it('shows why a test-run was refused', async () => {
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([{ ...NEW_SITE, approved_version: 1, pending_changes: 0 }]);
    vi.spyOn(siteProfilesApi, 'get').mockResolvedValue(VERSION_1);
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({ ...PENDING, approved_version: 1, changes: [] });
    vi.spyOn(siteProfilesApi, 'testRunFunction').mockRejectedValue({ status: 422, detail: 'no readings in the window' });
    renderAt('/site-profiles/1001');
    fireEvent.mouseDown(await screen.findByRole('tab', { name: 'What the AI knows' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Try site-bess1-round-trip-efficiency' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).queryByLabelText('Device')).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Run' }));
    expect(await within(dialog).findByRole('alert')).toBeTruthy();
  });

  it('does not call an onboarded site "not onboarded" while its profile loads', async () => {
    let resolveProfile: (profile: ProfileVersion) => void = () => {};
    vi.spyOn(siteProfilesApi, 'list').mockResolvedValue([]);
    vi.spyOn(siteProfilesApi, 'get').mockReturnValue(new Promise(resolve => { resolveProfile = resolve; }));
    vi.spyOn(siteProfilesApi, 'changes').mockResolvedValue({ ...PENDING, approved_version: 1, changes: [] });
    renderAt('/site-profiles/1001');
    expect(await screen.findByText('Loading the profile...')).toBeTruthy();
    expect(screen.queryByText(/Not onboarded/)).toBeNull();
    resolveProfile(VERSION_1);
    expect(await screen.findByText('The AI uses profile version 1.')).toBeTruthy();
  });
});
