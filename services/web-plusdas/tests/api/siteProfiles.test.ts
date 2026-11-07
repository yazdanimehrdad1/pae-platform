import { afterEach, describe, expect, it, vi } from 'vitest';
import { siteProfilesApi } from '@/api/siteProfiles';

function stubFetch(status = 200, body: unknown = {}) {
  const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const call = (fetchMock: ReturnType<typeof stubFetch>, index = 0) => {
  const [url, init] = fetchMock.mock.calls[index];
  return { url, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body) : undefined };
};

afterEach(() => vi.unstubAllGlobals());

describe('siteProfilesApi (intelli-gateway, same origin, admins only)', () => {
  it('lists and syncs every site', async () => {
    const fetchMock = stubFetch(200, []);
    await siteProfilesApi.list();
    await siteProfilesApi.syncAll();
    expect(call(fetchMock, 0)).toEqual({ url: '/intelli-gateway-api/v1/site-profiles', method: 'GET', body: undefined });
    expect(call(fetchMock, 1)).toEqual({ url: '/intelli-gateway-api/v1/site-profiles/sync', method: 'POST', body: {} });
  });

  it("reads one site's profile, versions and pending changes, and syncs it", async () => {
    const fetchMock = stubFetch(200, {});
    await siteProfilesApi.get(1001);
    await siteProfilesApi.versions(1001);
    await siteProfilesApi.changes(1001);
    await siteProfilesApi.sync(1001);
    expect(fetchMock.mock.calls.map(([url, init]) => `${init.method ?? 'GET'} ${url}`)).toEqual([
      'GET /intelli-gateway-api/v1/sites/1001/profile',
      'GET /intelli-gateway-api/v1/sites/1001/profile/versions',
      'GET /intelli-gateway-api/v1/sites/1001/profile/changes',
      'POST /intelli-gateway-api/v1/sites/1001/profile/sync',
    ]);
  });

  it('approves the chosen changes against the read that was reviewed', async () => {
    const fetchMock = stubFetch(200, {});
    await siteProfilesApi.approve(1001, { change_ids: ['site', 'device:1'], fetched_at: '2026-11-07T10:00:00Z' });
    expect(call(fetchMock)).toEqual({
      url: '/intelli-gateway-api/v1/sites/1001/profile/approve',
      method: 'POST',
      body: { change_ids: ['site', 'device:1'], fetched_at: '2026-11-07T10:00:00Z' },
    });
  });

  it('rejects with the status, so the page can tell "re-review" (409) from other errors', async () => {
    stubFetch(409, { detail: 'backend-ot was read again since; review the changes again' });
    await expect(siteProfilesApi.approve(1001, {})).rejects.toMatchObject({ status: 409 });
  });
});
