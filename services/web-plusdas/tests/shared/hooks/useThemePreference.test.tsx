// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { meApi } from '@/api/me';
import type { Preference } from '@/api/types/me';
import { ThemeProvider } from '@/shared/components/theme-provider';
import { useThemePreference } from '@/shared/hooks/useThemePreference';

const STORAGE_KEY = 'vite-ui-theme';
const saved = (value: unknown): Preference => ({ key: 'theme', value, updated_at: '2026-11-01T00:00:00Z' } as Preference);

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey={STORAGE_KEY}>{children}</ThemeProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(meApi, 'putPreference').mockImplementation(async (key, value) => ({ key, value, updated_at: '2026-11-01T00:00:00Z' }) as Preference);
});

afterEach(() => vi.restoreAllMocks());

describe('useThemePreference', () => {
  it("is dark for a user who never chose, whatever this browser showed last", async () => {
    window.localStorage.setItem(STORAGE_KEY, 'light'); // another user's choice in this browser
    vi.spyOn(meApi, 'listPreferences').mockResolvedValue([]);
    const { result } = renderHook(() => useThemePreference(), { wrapper });
    await waitFor(() => expect(result.current[0]).toBe('dark'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(meApi.putPreference).not.toHaveBeenCalled();
  });

  it("follows the user's saved choice", async () => {
    vi.spyOn(meApi, 'listPreferences').mockResolvedValue([saved('light')]);
    const { result } = renderHook(() => useThemePreference(), { wrapper });
    await waitFor(() => expect(result.current[0]).toBe('light'));
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('light'); // the next page load starts light
  });

  it('switches at once and saves the choice to the account', async () => {
    vi.spyOn(meApi, 'listPreferences').mockResolvedValue([]);
    const { result } = renderHook(() => useThemePreference(), { wrapper });
    await waitFor(() => expect(meApi.listPreferences).toHaveBeenCalled());
    act(() => result.current[1]('light'));
    expect(result.current[0]).toBe('light');
    await waitFor(() => expect(meApi.putPreference).toHaveBeenCalledWith('theme', 'light'));
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(result.current[0]).toBe('light'); // not flipped back by the stored default
  });

  it("keeps this browser's theme when the preferences can't load", async () => {
    window.localStorage.setItem(STORAGE_KEY, 'light');
    vi.spyOn(meApi, 'listPreferences').mockRejectedValue(new Error('offline'));
    const { result } = renderHook(() => useThemePreference(), { wrapper });
    await waitFor(() => expect(meApi.listPreferences).toHaveBeenCalled());
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(result.current[0]).toBe('light');
  });

  it('ignores a stored value that is not a theme', async () => {
    vi.spyOn(meApi, 'listPreferences').mockResolvedValue([saved('purple')]);
    const { result } = renderHook(() => useThemePreference(), { wrapper });
    await waitFor(() => expect(result.current[0]).toBe('dark'));
  });
});
