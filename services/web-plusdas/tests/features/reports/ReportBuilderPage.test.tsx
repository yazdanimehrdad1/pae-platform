// @vitest-environment jsdom
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { devicesApi, reportsApi, sitesApi } from '@/api';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { ReportCatalogRecord, ReportRunRecord, ReportTemplateRecord } from '@/api/types/reports';
import type { Site } from '@/api/types/sites';
import ReportBuilderPage from '@/features/reports/ReportBuilderPage';
import { blankDefinition } from '@/features/reports/lib/draft';

const CATALOG: ReportCatalogRecord = {
  site_id: 1001, timezone: 'America/Los_Angeles', max_window_days: 92,
  block_kinds: ['text', 'kpi', 'chart', 'point_stats_table', 'alarm_events_table'],
  point_stats: ['min', 'max', 'avg', 'first', 'last', 'count'],
  site_functions: [{ name: 'site-energy-summary', kind: 'site', output: 'scalar', summary: 'Energy', numeric_fields: ['energy_kwh'] }],
};

const TEMPLATE: ReportTemplateRecord = {
  id: 4, site_id: 1001, name: 'Daily energy', description: 'Yesterday', version: 2,
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
  definition: blankDefinition(),
};

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // Radix Select scrolls the chosen option into view
});

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(sitesApi, 'getAll').mockResolvedValue([{ id: '1001', name: 'Alpha Solar Farm', timezone: 'America/Los_Angeles' }] as Site[]);
  vi.spyOn(reportsApi, 'getCatalog').mockResolvedValue(CATALOG);
  vi.spyOn(reportsApi, 'getTemplate').mockResolvedValue(structuredClone(TEMPLATE));
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([] as DevicePointsEntry[]);
  vi.spyOn(reportsApi, 'requestRun').mockResolvedValue({ id: 77 } as ReportRunRecord);
  vi.spyOn(reportsApi, 'createTemplate').mockImplementation(async (_siteId, payload) => ({ ...TEMPLATE, id: 9, name: payload.name }));
  vi.spyOn(reportsApi, 'updateTemplate').mockImplementation(async () => ({ ...TEMPLATE, version: 3 }));
});

function renderPage(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/reports/:siteId/builder" element={<ReportBuilderPage />} />
          <Route path="/reports/:siteId/runs/:runId" element={<p>report page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function addSection(label: string) {
  const trigger = screen.getByRole('button', { name: 'Add section' });
  fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false });
  fireEvent.click(await screen.findByRole('menuitem', { name: label }));
}

describe('ReportBuilderPage', () => {
  it('starts a new report with a summary and generates it inline, then opens it', async () => {
    renderPage('/reports/1001/builder');
    expect(await screen.findByRole('heading', { name: 'New report' })).toBeTruthy();
    expect(await screen.findByText('Alpha Solar Farm · times in America/Los_Angeles')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Quick look' } });
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }));
    await waitFor(() => expect(reportsApi.requestRun).toHaveBeenCalledWith('1001', { definition: blankDefinition(), name: 'Quick look' }));
    expect(await screen.findByText('report page')).toBeTruthy();
  });

  it('blocks generating until a new section is filled in', async () => {
    renderPage('/reports/1001/builder');
    await screen.findByRole('heading', { name: 'New report' });
    await addSection('Chart');
    const chart = screen.getByRole('region', { name: 'Section 2: Chart' });
    expect(within(chart).getByText('Series 1: choose a point')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Generate report' }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(within(chart).getByRole('button', { name: 'Remove section 2' }));
    expect((screen.getByRole('button', { name: 'Generate report' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('opens a template and generates it from the template while unchanged', async () => {
    renderPage('/reports/1001/builder?template=4');
    expect(await screen.findByRole('heading', { name: 'Template: Daily energy' })).toBeTruthy();
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Daily energy');
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }));
    await waitFor(() => expect(reportsApi.requestRun).toHaveBeenCalledWith('1001', { template_id: 4, name: 'Daily energy' }));
  });

  it('saves changes to the template, or as a new one', async () => {
    renderPage('/reports/1001/builder?template=4');
    await screen.findByRole('heading', { name: 'Template: Daily energy' });
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Daily energy v2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save template' }));
    await waitFor(() => expect(reportsApi.updateTemplate).toHaveBeenCalledWith('1001', 4, {
      name: 'Daily energy v2', description: 'Yesterday', definition: TEMPLATE.definition,
    }));

    fireEvent.click(screen.getByRole('button', { name: 'Save as new template' }));
    await waitFor(() => expect(reportsApi.createTemplate).toHaveBeenCalledWith('1001', expect.objectContaining({ name: 'Daily energy v2' })));
  });

  it("shows backend-ot's problems on the section they belong to", async () => {
    vi.spyOn(reportsApi, 'requestRun').mockRejectedValue({
      detail: { error: 'ValidationError', message: 'bad', errors: ['text_1: something is off', 'The report window is longer than 92 days'] },
    });
    renderPage('/reports/1001/builder');
    await screen.findByRole('heading', { name: 'New report' });
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }));
    const summary = screen.getByRole('region', { name: 'Section 1: Text' });
    expect(await within(summary).findByText('something is off')).toBeTruthy();
    expect(screen.getByText('The report window is longer than 92 days')).toBeTruthy();
  });

  it('needs a name to save a template', async () => {
    renderPage('/reports/1001/builder');
    await screen.findByRole('heading', { name: 'New report' });
    expect((screen.getByRole('button', { name: 'Save as template' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Mine' } });
    expect((screen.getByRole('button', { name: 'Save as template' }) as HTMLButtonElement).disabled).toBe(false);
  });
});
