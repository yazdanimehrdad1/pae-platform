// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { meApi } from '@/api/me';
import type { Preference } from '@/api/types/me';
import { usePreference } from '@/shared/hooks/usePreference';

const isString = (value: unknown): value is string => typeof value === 'string';
const stored = (key: string, value: unknown): Preference => ({ key, value: value as Preference['value'], updated_at: '2026-11-01T00:00:00Z' });

function wrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

afterEach(() => vi.restoreAllMocks());

describe('usePreference', () => {
  it('is the fallback until loaded, then the stored value', async () => {
    vi.spyOn(meApi, 'listPreferences').mockResolvedValue([stored('colour', 'blue')]);
    const { result } = renderHook(() => usePreference('colour', 'red', isString), { wrapper: wrapper() });
    expect(result.current[0]).toBe('red');
    await waitFor(() => expect(result.current[0]).toBe('blue'));
    expect(result.current[2].isLoaded).toBe(true);
  });

  it('keeps a value set while the preferences are still loading', async () => {
    let finishLoading: (preferences: Preference[]) => void = () => {};
    vi.spyOn(meApi, 'listPreferences').mockReturnValue(new Promise(resolve => { finishLoading = resolve; }));
    let finishSaving: () => void = () => {};
    vi.spyOn(meApi, 'putPreference').mockReturnValue(new Promise(resolve => { finishSaving = () => resolve(stored('colour', 'green')); }));
    const { result } = renderHook(() => usePreference('colour', 'red', isString), { wrapper: wrapper() });

    act(() => result.current[1]('green'));
    await act(async () => finishLoading([stored('colour', 'blue')])); // the older stored value
    await waitFor(() => expect(result.current[2].isLoaded).toBe(true));
    expect(result.current[0]).toBe('green');
    await act(async () => finishSaving());
    expect(meApi.putPreference).toHaveBeenCalledWith('colour', 'green');
  });

  it('saves the changes to one key in order', async () => {
    vi.spyOn(meApi, 'listPreferences').mockResolvedValue([]);
    const saved: unknown[] = [];
    vi.spyOn(meApi, 'putPreference').mockImplementation(async (key, value) => {
      await new Promise(resolve => setTimeout(resolve, value === 'first' ? 20 : 0));
      saved.push(value);
      return stored(key, value);
    });
    const { result } = renderHook(() => usePreference('colour', 'red', isString), { wrapper: wrapper() });
    await waitFor(() => expect(result.current[2].isLoaded).toBe(true));
    act(() => result.current[1]('first'));
    act(() => result.current[1]('second'));
    await waitFor(() => expect(saved).toEqual(['first', 'second']));
  });

  it('falls back to the default for a value of the wrong type', async () => {
    vi.spyOn(meApi, 'listPreferences').mockResolvedValue([stored('colour', 42)]);
    const { result } = renderHook(() => usePreference('colour', 'red', isString), { wrapper: wrapper() });
    await waitFor(() => expect(result.current[2].isLoaded).toBe(true));
    expect(result.current[0]).toBe('red');
  });
});
