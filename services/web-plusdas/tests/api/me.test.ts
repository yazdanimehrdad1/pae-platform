import { afterEach, describe, expect, it, vi } from 'vitest';
import { authApi, meApi, usersApi } from '@/api/me';

function stubFetch(status = 200, body: unknown = {}) {
  const fetchMock = vi.fn().mockImplementation(async () => new Response(status === 204 ? null : JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const call = (fetchMock: ReturnType<typeof stubFetch>, index = 0) => {
  const [url, init] = fetchMock.mock.calls[index];
  return { url, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body) : undefined };
};

afterEach(() => vi.unstubAllGlobals());

describe('authApi (intelli-gateway, same origin; the session is a cookie, never in the body)', () => {
  it('logs in, out, and asks who is logged in', async () => {
    const fetchMock = stubFetch(200, { id: 1, email: 'ana@example.com', display_name: 'Ana', role: 'admin' });
    await authApi.login({ email: 'ana@example.com', password: 'secret' });
    await authApi.me();
    expect(call(fetchMock, 0)).toEqual({ url: '/intelli-gateway-api/v1/auth/login', method: 'POST', body: { email: 'ana@example.com', password: 'secret' } });
    expect(call(fetchMock, 1)).toEqual({ url: '/intelli-gateway-api/v1/me', method: 'GET', body: undefined });

    const logoutMock = stubFetch(204);
    await authApi.logout();
    expect(call(logoutMock)).toEqual({ url: '/intelli-gateway-api/v1/auth/logout', method: 'POST', body: undefined });
  });
});

describe('meApi', () => {
  it('saves a preference by its (escaped) key, wrapping the value', async () => {
    const fetchMock = stubFetch(200, { key: 'live-data.configs', value: {}, updated_at: '' });
    await meApi.putPreference('live-data.configs', { 1: { alias: 'BESS' } });
    expect(call(fetchMock)).toEqual({
      url: '/intelli-gateway-api/v1/me/preferences/live-data.configs', method: 'PUT', body: { value: { 1: { alias: 'BESS' } } },
    });
  });

  it('creates, edits, reorders and deletes trends', async () => {
    const fetchMock = stubFetch(200, []);
    const trend = { name: 'BESS', points: ['101'], scale: null, styles: null };
    await meApi.createTrend(trend);
    await meApi.updateTrend(7, trend);
    await meApi.reorderTrends([7, 3]);
    expect(call(fetchMock, 0)).toEqual({ url: '/intelli-gateway-api/v1/me/trends', method: 'POST', body: trend });
    expect(call(fetchMock, 1)).toEqual({ url: '/intelli-gateway-api/v1/me/trends/7', method: 'PUT', body: trend });
    expect(call(fetchMock, 2)).toEqual({ url: '/intelli-gateway-api/v1/me/trends/order', method: 'PUT', body: { trend_ids: [7, 3] } });
    const deleteMock = stubFetch(204);
    await meApi.deleteTrend(7);
    expect(call(deleteMock)).toEqual({ url: '/intelli-gateway-api/v1/me/trends/7', method: 'DELETE', body: undefined });
  });

  it('creates and edits notes', async () => {
    const fetchMock = stubFetch(200, {});
    await meApi.createNote({ content: 'check INV2' });
    await meApi.updateNote(4, 'INV2 fixed');
    expect(call(fetchMock, 0)).toEqual({ url: '/intelli-gateway-api/v1/me/notes', method: 'POST', body: { content: 'check INV2' } });
    expect(call(fetchMock, 1)).toEqual({ url: '/intelli-gateway-api/v1/me/notes/4', method: 'PUT', body: { content: 'INV2 fixed' } });
  });
});

describe('usersApi (admins) and changing your own password', () => {
  it('lists, adds, edits and resets passwords on /v1/users', async () => {
    const fetchMock = stubFetch(200, {});
    await usersApi.list();
    await usersApi.create({ email: 'bob@example.com', display_name: 'Bob', role: 'monitor', password: 'long enough password' });
    await usersApi.update(3, { role: 'engineer', disabled: true });
    expect(call(fetchMock, 0)).toEqual({ url: '/intelli-gateway-api/v1/users', method: 'GET', body: undefined });
    expect(call(fetchMock, 1).method).toBe('POST');
    expect(call(fetchMock, 2)).toEqual({ url: '/intelli-gateway-api/v1/users/3', method: 'PATCH', body: { role: 'engineer', disabled: true } });

    const noContent = stubFetch(204);
    await usersApi.resetPassword(3, 'a new password');
    await authApi.changePassword({ current_password: 'old one', new_password: 'a new password' });
    expect(call(noContent, 0)).toEqual({ url: '/intelli-gateway-api/v1/users/3/password', method: 'PUT', body: { password: 'a new password' } });
    expect(call(noContent, 1)).toEqual({
      url: '/intelli-gateway-api/v1/me/password', method: 'PUT', body: { current_password: 'old one', new_password: 'a new password' },
    });
  });
});
