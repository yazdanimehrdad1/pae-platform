// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { reportsApi } from '@/api';
import type { ReportRunRecord } from '@/api/types/reports';
import ReportViewPage from '@/features/reports/ReportViewPage';

const DEFINITION: ReportRunRecord['definition'] = {
  schema_version: 1,
  window: { kind: 'calendar', period: 'day', offset: -1 },
  blocks: [{ kind: 'text', id: 'intro', body: 'x' }],
};

const RUN: ReportRunRecord = {
  id: 7, site_id: 1001, template_id: 4, template_version: 1, name: 'Daily energy', status: 'succeeded', trigger: 'manual',
  window_start: '2026-10-12T07:00:00Z', window_end: '2026-10-13T07:00:00Z', requested_at: '2026-10-13T08:00:00Z',
  definition: DEFINITION,
  result: {
    schema_version: 1, site_id: 1001, site_name: 'Alpha Solar Farm', timezone: 'America/Los_Angeles',
    window_start: '2026-10-12T07:00:00Z', window_end: '2026-10-13T07:00:00Z', generated_at: '2026-10-13T08:00:05Z',
    definition: DEFINITION,
    blocks: [
      { kind: 'text', block_id: 'intro', title: 'Summary', body: 'Alpha Solar Farm, yesterday' },
      { kind: 'kpi', block_id: 'kpis', items: [
        { label: 'Energy', value: 1234.5, unit: 'kWh' },
        { label: 'Availability', value: null, unit: '%', error: 'no inverter_state point' },
      ] },
      { kind: 'chart', block_id: 'power', title: 'Power', style: 'line', series: [] },
      { kind: 'point_stats_table', block_id: 'stats', title: 'Statistics', stats: ['max', 'count'], bucket: 'none', rows: [
        { point_id: 1, point_name: 'active_power', device_id: 2, device_name: 'meter_1', unit: 'kW', values: { max: 42, count: 10 } },
      ] },
      { kind: 'alarm_events_table', block_id: 'alarms', title: 'Alarms', total_count: 3, rows: [
        { event_id: 5, alarm_name: 'meter_comms', severity: 'fault', device_id: 2, device_name: 'meter_1', raised_at: '2026-10-12T15:00:00Z', cleared_at: null, duration_seconds: 900, message: 'lost' },
      ] },
      { kind: 'chart', block_id: 'poi', title: 'POI power', style: 'line', error: 'no POI point on this site' },
    ],
  },
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(reportsApi, 'getRun').mockResolvedValue(structuredClone(RUN));
});

afterEach(() => document.documentElement.classList.remove('dark'));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/reports/1001/runs/7']}>
        <Routes><Route path="/reports/:siteId/runs/:runId" element={<ReportViewPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const section = (title: string) => screen.getByRole('heading', { name: title }).closest('section')!;

describe('ReportViewPage', () => {
  it('renders every block from the stored report, in site time', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { level: 1, name: 'Daily energy' })).toBeTruthy();
    expect(reportsApi.getRun).toHaveBeenCalledWith('1001', 7);
    expect(screen.getByText('Alpha Solar Farm · 12 Oct 2026, 00:00 – 13 Oct 2026, 00:00 (America/Los_Angeles)')).toBeTruthy();
    expect(screen.getByText('Alpha Solar Farm, yesterday')).toBeTruthy();
    expect(screen.getByText('1,235 kWh')).toBeTruthy();
    expect(screen.getByText('no inverter_state point')).toBeTruthy();
    expect(within(section('Power')).getByText('No readings in this period.')).toBeTruthy();
    expect(within(section('Statistics')).getByText('42 kW')).toBeTruthy();
    expect(within(section('Statistics')).getByText('10')).toBeTruthy(); // a count has no unit
    const alarms = within(section('Alarms'));
    expect(alarms.getByText('meter_comms')).toBeTruthy();
    expect(alarms.getByText('Fault')).toBeTruthy();
    expect(alarms.getByText('Active')).toBeTruthy();
    expect(alarms.getByText('15 min')).toBeTruthy();
    expect(alarms.getByText('Showing the newest 1 of 3 events.')).toBeTruthy();
  });

  it('shows a failed block as an error without hiding the rest', async () => {
    renderPage();
    const poi = await screen.findByRole('heading', { name: 'POI power' });
    expect(within(poi.closest('section')!).getByText('This section could not be generated: no POI point on this site')).toBeTruthy();
  });

  it('exports a PDF through the print dialog, in the light theme', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    document.documentElement.classList.add('dark');
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Export PDF' }));
    expect(print).toHaveBeenCalledOnce();

    window.dispatchEvent(new Event('beforeprint'));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    window.dispatchEvent(new Event('afterprint'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('downloads a table as CSV', async () => {
    const createObjectURL = vi.fn(() => 'blob:report');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    renderPage();
    await screen.findByRole('heading', { name: 'Statistics' });
    fireEvent.click(within(section('Statistics')).getByRole('button', { name: 'CSV' }));
    expect(createObjectURL).toHaveBeenCalledOnce();
    const anchor = click.mock.instances[0] as unknown as HTMLAnchorElement;
    expect(anchor.download).toBe('daily-energy-stats.csv');
    vi.unstubAllGlobals();
  });

  it('shows a report that is still generating', async () => {
    vi.spyOn(reportsApi, 'getRun').mockResolvedValue({ ...structuredClone(RUN), status: 'running', result: null });
    renderPage();
    expect(await screen.findByText('Generating')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Export PDF' })).toBeNull();
  });
});
