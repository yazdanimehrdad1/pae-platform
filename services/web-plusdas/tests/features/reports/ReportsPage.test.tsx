// @vitest-environment jsdom
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { reportsApi, sitesApi } from '@/api';
import type { ReportRunRecord, ReportRunSummary, ReportScheduleRecord, ReportTemplateRecord } from '@/api/types/reports';
import type { Site } from '@/api/types/sites';
import ReportsPage from '@/features/reports/ReportsPage';

const TEMPLATE: ReportTemplateRecord = {
  id: 4, site_id: 1001, name: 'Daily energy', description: 'Yesterday at a glance', version: 1,
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
  definition: { schema_version: 1, window: { kind: 'calendar', period: 'day', offset: -1 }, blocks: [{ kind: 'text', id: 'intro', body: 'x' }] },
};

const run = (id: number, status: ReportRunSummary['status'], extra: Partial<ReportRunSummary> = {}): ReportRunSummary => ({
  id, site_id: 1001, template_id: 4, template_version: 1, name: `Report ${id}`, status, trigger: 'manual',
  window_start: '2026-10-12T07:00:00Z', window_end: '2026-10-13T07:00:00Z', requested_at: '2026-10-13T08:00:00Z',
  ...extra,
});

let runs: ReportRunSummary[];
let schedules: ReportScheduleRecord[];

const SCHEDULE: ReportScheduleRecord = {
  id: 2, site_id: 1001, template_id: 4, template_name: 'Daily energy', timezone: 'America/Los_Angeles',
  cadence: { kind: 'daily', time: '06:00' }, window_override: null, enabled: true, keep_last: 7, keep_days: null,
  next_run_at: '2026-10-14T13:00:00Z', last_run_at: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
};

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // Radix Select scrolls the chosen option into view
});

beforeEach(() => {
  vi.restoreAllMocks();
  runs = [run(2, 'failed', { error: 'Site 1001 no longer exists' }), run(1, 'succeeded', { trigger: 'schedule', schedule_id: 2 })];
  schedules = [structuredClone(SCHEDULE)];
  vi.spyOn(reportsApi, 'listSchedules').mockImplementation(async siteId => (siteId === '1001' ? structuredClone(schedules) : []));
  vi.spyOn(reportsApi, 'createSchedule').mockImplementation(async (_siteId, payload) => {
    const created = { ...SCHEDULE, id: 3, ...payload } as ReportScheduleRecord;
    schedules = [...schedules, created];
    return created;
  });
  vi.spyOn(reportsApi, 'updateSchedule').mockImplementation(async (_siteId, scheduleId, payload) => {
    schedules = schedules.map(schedule => (schedule.id === scheduleId ? { ...schedule, ...payload } as ReportScheduleRecord : schedule));
    return schedules.find(schedule => schedule.id === scheduleId)!;
  });
  vi.spyOn(reportsApi, 'deleteSchedule').mockImplementation(async (_siteId, scheduleId) => {
    const deleted = schedules.find(schedule => schedule.id === scheduleId)!;
    schedules = schedules.filter(schedule => schedule.id !== scheduleId);
    return deleted;
  });
  vi.spyOn(sitesApi, 'getAll').mockResolvedValue([
    { id: '1001', name: 'Alpha Solar Farm', timezone: 'America/Los_Angeles' },
    { id: '2002', name: 'Beta Yard', timezone: 'UTC' },
  ] as Site[]);
  vi.spyOn(reportsApi, 'listTemplates').mockImplementation(async siteId => (siteId === '1001' ? [TEMPLATE] : []));
  vi.spyOn(reportsApi, 'listRuns').mockImplementation(async siteId => (siteId === '1001' ? structuredClone(runs) : []));
  vi.spyOn(reportsApi, 'requestRun').mockImplementation(async () => {
    const queued = run(3, 'queued');
    runs = [queued, ...runs];
    return queued as ReportRunRecord;
  });
  vi.spyOn(reportsApi, 'deleteRuns').mockImplementation(async () => {
    const deleted = runs.length;
    runs = [];
    return { deleted };
  });
  vi.spyOn(reportsApi, 'deleteRun').mockImplementation(async (_siteId, runId) => {
    const deleted = runs.find(candidate => candidate.id === runId)!;
    runs = runs.filter(candidate => candidate.id !== runId);
    return deleted;
  });
});

function renderPage(path = '/reports') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}><ReportsPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

const reportsTable = () => screen.getByRole('link', { name: 'Report 1' }).closest('table')!;

describe('ReportsPage', () => {
  it("lists the first site's templates and reports, times in the site's zone", async () => {
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Daily energy' })).toBeTruthy();
    expect(screen.getByText('Yesterday · 1 section')).toBeTruthy();
    expect(await screen.findByText(/^Times in America\/Los_Angeles/)).toBeTruthy();
    // 07:00 UTC is midnight in Los Angeles (PDT)
    expect(within(reportsTable()).getAllByText('12 Oct 2026, 00:00 – 13 Oct 2026, 00:00')).toHaveLength(2);
  });

  it('links a ready report to its page and says why a failed one failed', async () => {
    renderPage();
    const link = await screen.findByRole('link', { name: 'Report 1' });
    expect(link.getAttribute('href')).toBe('/reports/1001/runs/1');
    expect(screen.queryByRole('link', { name: 'Report 2' })).toBeNull();
    expect(screen.getByText('Failed')).toBeTruthy();
    expect(screen.getByText('Site 1001 no longer exists')).toBeTruthy();
  });

  it('generates a report from a template and shows it queued', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Generate Daily energy' }));
    await waitFor(() => expect(reportsApi.requestRun).toHaveBeenCalledWith('1001', { template_id: 4 }));
    expect(await screen.findByText('Queued')).toBeTruthy();
  });

  it('deletes a report only after confirming', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Report 1' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(reportsApi.deleteRun).toHaveBeenCalledWith('1001', 1));
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Report 1' })).toBeNull());
  });

  it('deletes all reports of the site after confirming, and keeps the templates', async () => {
    renderPage();
    await screen.findByRole('link', { name: 'Report 1' });
    fireEvent.click(screen.getByRole('button', { name: 'Delete all' }));
    const dialog = await screen.findByRole('alertdialog');
    expect(within(dialog).getByText('Delete all reports of this site?')).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete all' }));
    await waitFor(() => expect(reportsApi.deleteRuns).toHaveBeenCalledWith('1001'));
    expect(await screen.findByText('No reports yet. Generate one from a template.')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Daily energy' })).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Delete all' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('lists schedules in words and marks their reports', async () => {
    renderPage();
    expect(await screen.findByText('Every day at 06:00')).toBeTruthy();
    expect(screen.getByText('Keeps the last 7 reports')).toBeTruthy();
    expect(screen.getByText('14 Oct 2026, 06:00')).toBeTruthy(); // next report, site time
    expect(within(reportsTable()).getByText('Scheduled')).toBeTruthy();
  });

  it('turns a schedule off', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('switch', { name: 'Turn off the Daily energy schedule' }));
    await waitFor(() => expect(reportsApi.updateSchedule).toHaveBeenCalledWith('1001', 2, { enabled: false }));
  });

  it("schedules a template from its card", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Schedule Daily energy' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Schedule a report')).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create schedule' }));
    await waitFor(() => expect(reportsApi.createSchedule).toHaveBeenCalledWith('1001', expect.objectContaining({
      template_id: 4, cadence: { kind: 'daily', time: '06:00' },
    })));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('changes a schedule without sending its template', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Change the Daily energy schedule' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('At'), { target: { value: '07:15' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save schedule' }));
    await waitFor(() => expect(reportsApi.updateSchedule).toHaveBeenCalledWith('1001', 2, {
      cadence: { kind: 'daily', time: '07:15' }, window_override: null, enabled: true, keep_last: 7, keep_days: null,
    }));
  });

  it('deletes a schedule after confirming', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Delete the Daily energy schedule' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(reportsApi.deleteSchedule).toHaveBeenCalledWith('1001', 2));
    expect(await screen.findByText('No schedules yet.')).toBeTruthy();
  });

  it('shows a report the server created (a schedule) without a reload', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      runs = [run(1, 'succeeded')];
      renderPage();
      expect(await screen.findByRole('link', { name: 'Report 1' })).toBeTruthy();

      // Nothing is pending, so only the slow refresh can find it.
      runs = [run(5, 'succeeded', { trigger: 'schedule', schedule_id: 2 }), ...runs];
      await act(() => vi.advanceTimersByTimeAsync(29_000));
      expect(screen.queryByRole('link', { name: 'Report 5' })).toBeNull();
      await act(() => vi.advanceTimersByTimeAsync(2_000));
      expect(await screen.findByRole('link', { name: 'Report 5' })).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it('opens on the site named in the URL', async () => {
    renderPage('/reports?site=2002');
    expect(await screen.findByText('No report templates for this site yet. Build one with New report.')).toBeTruthy();
    expect(reportsApi.listTemplates).toHaveBeenCalledWith('2002');
  });
});
