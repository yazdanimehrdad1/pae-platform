import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ReportDefinition } from '@/api/types/reports';
import { reportsApi } from '@/api/reports';

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const call = (fetchMock: ReturnType<typeof vi.fn>) => {
  const [url, init] = fetchMock.mock.calls[0];
  return { url: String(url), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(init.body) : undefined };
};

const DEFINITION: ReportDefinition = {
  schema_version: 1,
  window: { kind: 'calendar', period: 'day', offset: -1 },
  blocks: [{ kind: 'text', id: 'intro', body: 'Hello {site_name}' }],
};

afterEach(() => vi.unstubAllGlobals());

describe('reportsApi', () => {
  it('reads the catalog and templates of a site', async () => {
    let fetchMock = stubFetch(200, {});
    await reportsApi.getCatalog('1001');
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/catalog', method: 'GET' });

    fetchMock = stubFetch(200, []);
    await reportsApi.listTemplates('1001');
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/templates', method: 'GET' });
  });

  it('creates, updates and deletes templates', async () => {
    let fetchMock = stubFetch(201, {});
    await reportsApi.createTemplate('1001', { name: 'Daily', description: '', definition: DEFINITION });
    expect(call(fetchMock)).toEqual({
      url: '/api/reports/site/1001/templates', method: 'POST', body: { name: 'Daily', description: '', definition: DEFINITION },
    });

    fetchMock = stubFetch(200, {});
    await reportsApi.updateTemplate('1001', 4, { name: 'Daily v2' });
    expect(call(fetchMock)).toEqual({ url: '/api/reports/site/1001/templates/4', method: 'PUT', body: { name: 'Daily v2' } });

    fetchMock = stubFetch(200, {});
    await reportsApi.deleteTemplate('1001', 4);
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/templates/4', method: 'DELETE' });
  });

  it('requests a run from a template and lists runs with only the filters given', async () => {
    let fetchMock = stubFetch(202, {});
    await reportsApi.requestRun('1001', { template_id: 4 });
    expect(call(fetchMock)).toEqual({ url: '/api/reports/site/1001/runs', method: 'POST', body: { template_id: 4 } });

    fetchMock = stubFetch(200, []);
    await reportsApi.listRuns('1001');
    expect(call(fetchMock).url).toBe('/api/reports/site/1001/runs');

    fetchMock = stubFetch(200, []);
    await reportsApi.listRuns('1001', { templateId: 4, status: 'failed', limit: 10 });
    const url = new URL(call(fetchMock).url, 'http://host');
    expect(url.pathname).toBe('/api/reports/site/1001/runs');
    expect(Object.fromEntries(url.searchParams)).toEqual({ template_id: '4', status: 'failed', limit: '10' });
  });

  it('gets, deletes and reruns a run', async () => {
    let fetchMock = stubFetch(200, {});
    await reportsApi.getRun('1001', 9);
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/runs/9', method: 'GET' });

    fetchMock = stubFetch(200, {});
    await reportsApi.deleteRun('1001', 9);
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/runs/9', method: 'DELETE' });

    fetchMock = stubFetch(200, { deleted: 3 });
    expect(await reportsApi.deleteRuns('1001')).toEqual({ deleted: 3 });
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/runs', method: 'DELETE' });

    fetchMock = stubFetch(202, {});
    await reportsApi.rerun('1001', 9);
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/runs/9/rerun', method: 'POST' });
  });

  it("lists, creates, changes and deletes schedules, and lists a schedule's runs", async () => {
    let fetchMock = stubFetch(200, []);
    await reportsApi.listSchedules('1001');
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/schedules', method: 'GET' });

    const create = { template_id: 4, cadence: { kind: 'daily' as const, time: '06:00' }, enabled: true, keep_last: 7 };
    fetchMock = stubFetch(201, {});
    await reportsApi.createSchedule('1001', create);
    expect(call(fetchMock)).toEqual({ url: '/api/reports/site/1001/schedules', method: 'POST', body: create });

    fetchMock = stubFetch(200, {});
    await reportsApi.updateSchedule('1001', 2, { enabled: false, keep_last: null });
    expect(call(fetchMock)).toEqual({ url: '/api/reports/site/1001/schedules/2', method: 'PUT', body: { enabled: false, keep_last: null } });

    fetchMock = stubFetch(200, {});
    await reportsApi.deleteSchedule('1001', 2);
    expect(call(fetchMock)).toMatchObject({ url: '/api/reports/site/1001/schedules/2', method: 'DELETE' });

    fetchMock = stubFetch(200, []);
    await reportsApi.listRuns('1001', { scheduleId: 2 });
    expect(call(fetchMock).url).toBe('/api/reports/site/1001/runs?schedule_id=2');
  });

  it("surfaces backend-ot's list of problems", async () => {
    stubFetch(400, { detail: { error: 'ValidationError', message: 'bad', errors: ['chart: point 9 is not on this site'] } });
    await expect(reportsApi.requestRun('1001', { definition: DEFINITION })).rejects.toMatchObject({
      detail: { errors: ['chart: point 9 is not on this site'] },
    });
  });
});
