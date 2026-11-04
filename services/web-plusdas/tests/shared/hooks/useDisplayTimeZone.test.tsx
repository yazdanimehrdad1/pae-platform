// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { meApi } from '@/api/me';
import type { Preference } from '@/api/types/me';
import { BROWSER_TIME_ZONE, useDisplayTimeZone } from '@/shared/hooks/useDisplayTimeZone';

// A zone that differs from the machine running the tests, whatever that is.
const SITE_ZONE = BROWSER_TIME_ZONE === 'Asia/Tokyo' ? 'Europe/Berlin' : 'Asia/Tokyo';

function wrapperWith(preferences: Preference[]) {
  vi.spyOn(meApi, 'listPreferences').mockResolvedValue(preferences);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.spyOn(meApi, 'putPreference').mockImplementation(async (key, value) => ({ key, value, updated_at: '2026-11-01T00:00:00Z' }) as Preference);
});

afterEach(() => vi.restoreAllMocks());

describe('useDisplayTimeZone', () => {
  it("shows the site's zone by default", () => {
    const { result } = renderHook(() => useDisplayTimeZone(SITE_ZONE), { wrapper: wrapperWith([]) });
    expect(result.current).toMatchObject({ display: 'site', timeZone: SITE_ZONE, siteTimeZone: SITE_ZONE });
  });

  it("follows the user's saved choice", async () => {
    const wrapper = wrapperWith([{ key: 'time-display', value: 'browser', updated_at: '2026-11-01T00:00:00Z' }]);
    const { result } = renderHook(() => useDisplayTimeZone(SITE_ZONE), { wrapper });
    await waitFor(() => expect(result.current.timeZone).toBe(BROWSER_TIME_ZONE));
  });

  it("switches to the browser's zone, saves it for the user, and every page follows", async () => {
    const wrapper = wrapperWith([]);
    const { result } = renderHook(() => ({ first: useDisplayTimeZone(SITE_ZONE), second: useDisplayTimeZone('UTC') }), { wrapper });
    await waitFor(() => expect(meApi.listPreferences).toHaveBeenCalled());
    act(() => result.current.first.setDisplay('browser'));
    await waitFor(() => expect(result.current.first.timeZone).toBe(BROWSER_TIME_ZONE));
    expect(result.current.second.timeZone).toBe(BROWSER_TIME_ZONE);
    await waitFor(() => expect(meApi.putPreference).toHaveBeenCalledWith('time-display', 'browser'));
  });

  it("uses the browser's zone while the site's isn't known", () => {
    const { result } = renderHook(() => useDisplayTimeZone(undefined), { wrapper: wrapperWith([]) });
    expect(result.current).toMatchObject({ timeZone: BROWSER_TIME_ZONE, siteTimeZone: null });
  });

  it('ignores a stored value it does not know', async () => {
    const wrapper = wrapperWith([{ key: 'time-display', value: 'moon', updated_at: '2026-11-01T00:00:00Z' }]);
    const { result } = renderHook(() => useDisplayTimeZone(SITE_ZONE), { wrapper });
    await waitFor(() => expect(meApi.listPreferences).toHaveBeenCalled());
    expect(result.current.timeZone).toBe(SITE_ZONE);
  });
});
