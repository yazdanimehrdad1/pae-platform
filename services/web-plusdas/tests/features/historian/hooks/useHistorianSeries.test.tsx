// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import { historianApi } from '@/api/historian';
import type { DevicePointsEntry } from '@/api/types/devices';
import { AUTO_REFRESH_MS, useHistorianSeries } from '@/features/historian/hooks/useHistorianSeries';

const DEVICE = { deviceId: 2, deviceName: 'bess-1', deviceType: 'BESS', groups: {}, points: [{ id: 7, name: 'soc' }] } as unknown as DevicePointsEntry;

function renderSeries(autoRefresh: boolean) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  const rendered = renderHook(({ auto }) => useHistorianSeries('1001', ['7'], { preset: '1H' }, { autoRefresh: auto }), {
    wrapper, initialProps: { auto: autoRefresh },
  });
  return { ...rendered, queryClient };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([DEVICE]);
  vi.spyOn(historianApi, 'getDevicePointReadings').mockResolvedValue({ meta: {}, readings: {} } as never);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const fetches = () => vi.mocked(historianApi.getDevicePointReadings).mock.calls.length;

describe('useHistorianSeries refresh', () => {
  it('fetches once, then not on a timer, on focus or on reconnect while auto refresh is off', async () => {
    renderSeries(false);
    await waitFor(() => expect(fetches()).toBe(1));

    await act(() => vi.advanceTimersByTimeAsync(AUTO_REFRESH_MS * 3));
    window.dispatchEvent(new Event('focus'));
    window.dispatchEvent(new Event('visibilitychange'));
    window.dispatchEvent(new Event('online'));
    await act(() => vi.advanceTimersByTimeAsync(1_000));
    expect(fetches()).toBe(1);
  });

  it('refetches every minute while auto refresh is on, and stops when it is turned off', async () => {
    const { rerender } = renderSeries(true);
    await waitFor(() => expect(fetches()).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(AUTO_REFRESH_MS + 100));
    await waitFor(() => expect(fetches()).toBe(2));

    rerender({ auto: false });
    await act(() => vi.advanceTimersByTimeAsync(AUTO_REFRESH_MS * 2));
    expect(fetches()).toBe(2);
  });

  it('refetches when the Refresh button invalidates it', async () => {
    const { queryClient } = renderSeries(false);
    await waitFor(() => expect(fetches()).toBe(1));
    await act(() => queryClient.invalidateQueries({ queryKey: ['historian-series', '1001'] }));
    await waitFor(() => expect(fetches()).toBe(2));
  });
});
