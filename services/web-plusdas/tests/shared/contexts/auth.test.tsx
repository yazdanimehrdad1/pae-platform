// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { authApi } from '@/api/me';
import { client, isUnauthorized } from '@/api/client';
import type { MeResponse } from '@/api/types/me';
import { AuthProvider, useAuth } from '@/shared/contexts/auth';

const ANA: MeResponse = { id: 3, email: 'ana@example.com', display_name: 'Ana R', role: 'admin' };
const unauthorized = { detail: 'not logged in', status: 401 };

function renderAuth() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}><AuthProvider>{children}</AuthProvider></QueryClientProvider>
  );
  return { ...renderHook(() => useAuth(), { wrapper }), queryClient };
}

afterEach(() => vi.restoreAllMocks());

describe('AuthProvider', () => {
  it('starts logged out when there is no session', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValue(unauthorized);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
  });

  it('picks up an existing session (the cookie) on load', async () => {
    vi.spyOn(authApi, 'me').mockResolvedValue(ANA);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual({ id: '3', email: 'ana@example.com', name: 'Ana R', role: 'admin' }));
  });

  it('logs in, and a wrong password rejects with a 401', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValue(unauthorized);
    const login = vi.spyOn(authApi, 'login').mockRejectedValueOnce(unauthorized).mockResolvedValueOnce(ANA);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const error = await result.current.login('ana@example.com', 'wrong').catch((caught: unknown) => caught);
    expect(isUnauthorized(error)).toBe(true);
    await act(async () => { await result.current.login('ana@example.com', 'right'); });
    expect(login).toHaveBeenLastCalledWith({ email: 'ana@example.com', password: 'right' });
    expect(result.current.user?.email).toBe('ana@example.com');
  });

  it('ends the session when any API answers 401 (expired, or logged out elsewhere)', async () => {
    vi.spyOn(authApi, 'me').mockResolvedValue(ANA);
    const { result, queryClient } = renderAuth();
    await waitFor(() => expect(result.current.user).not.toBeNull());
    queryClient.setQueryData(['me', 'trends'], ['cached']);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'not logged in' }), { status: 401 })));

    await act(async () => { await client.get('/sites').catch(() => undefined); });

    expect(result.current.user).toBeNull();
    expect(queryClient.getQueryData(['me', 'trends'])).toBeUndefined();
    vi.unstubAllGlobals();
  });

  it('logs out through the API and forgets the user', async () => {
    vi.spyOn(authApi, 'me').mockResolvedValue(ANA);
    const logout = vi.spyOn(authApi, 'logout').mockResolvedValue(undefined);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).not.toBeNull());
    await act(async () => { await result.current.logout(); });
    expect(logout).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
  });
});
