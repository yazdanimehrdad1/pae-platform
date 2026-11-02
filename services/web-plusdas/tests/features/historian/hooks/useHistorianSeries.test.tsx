// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import { historianApi } from '@/api/historian';
import { forecastApi } from '@/api/forecast';
import type { DevicePointsEntry } from '@/api/types/devices';
import { AUTO_REFRESH_MS, isHistorianQueryOf, useHistorianSeries } from '@/features/historian/hooks/useHistorianSeries';

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

describe('useHistorianSeries while a new selection loads', () => {
  const TWO_POINT_DEVICE = { ...DEVICE, points: [{ id: 7, name: 'soc' }, { id: 8, name: 'power' }] } as unknown as DevicePointsEntry;
  const readingsOf = (pointIds: string[]) => ({
    meta: {},
    readings: Object.fromEntries(pointIds.map(pointId => [pointId, { timeseries: [{ time: '2026-10-21T12:00:00Z', value: Number(pointId) }] }])),
  });

  function renderSelection(initialPoints: string[]) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    return renderHook(({ points }) => useHistorianSeries('1001', points, { preset: '1H' }), { wrapper, initialProps: { points: initialPoints } });
  }

  it('keeps the last chart (fetching, not loading) until the new point arrives, then shows both', async () => {
    vi.mocked(devicesApi.getBySiteWithPoints).mockResolvedValue([TWO_POINT_DEVICE]);
    let release: () => void = () => {};
    vi.mocked(historianApi.getDevicePointReadings).mockImplementation(({ pointIds }) => (pointIds.length === 1
      ? Promise.resolve(readingsOf(pointIds))
      : new Promise(resolve => { release = () => resolve(readingsOf(pointIds)); })) as never);

    const { result, rerender } = renderSelection(['7']);
    await waitFor(() => expect(result.current.lines['7']).toHaveLength(1));

    rerender({ points: ['7', '8'] });
    await waitFor(() => expect(fetches()).toBe(2));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(true);
    expect(result.current.shownPoints).toEqual(['7']);
    expect(result.current.lines['7']).toHaveLength(1);

    await act(async () => release());
    await waitFor(() => expect(result.current.shownPoints).toEqual(['7', '8']));
    expect(result.current.lines['8']).toHaveLength(1);
  });

  it('drops a removed point at once, while the rest refetch', async () => {
    vi.mocked(devicesApi.getBySiteWithPoints).mockResolvedValue([TWO_POINT_DEVICE]);
    vi.mocked(historianApi.getDevicePointReadings).mockImplementation(({ pointIds }) => (pointIds.length === 2
      ? Promise.resolve(readingsOf(pointIds))
      : new Promise(() => {})) as never);

    const { result, rerender } = renderSelection(['7', '8']);
    await waitFor(() => expect(result.current.lines['8']).toHaveLength(1));

    rerender({ points: ['7'] });
    expect(result.current.isLoading).toBe(false);
    expect(result.current.shownPoints).toEqual(['7']);
    expect(Object.keys(result.current.lines)).toEqual(['7']);
  });

  it('is loading on the first fetch, with nothing to keep', async () => {
    vi.mocked(historianApi.getDevicePointReadings).mockImplementation(() => new Promise(() => {}) as never);
    const { result } = renderSelection(['7']);
    await waitFor(() => expect(fetches()).toBe(1));
    expect(result.current.isLoading).toBe(true);
  });
});

describe('useHistorianSeries PV forecast', () => {
  const FORECAST = {
    site_id: 1001, provider: 'open_meteo', source_kind: 'weather_model', fallback_used: false,
    issued_at: '2026-10-21T11:00:00Z', resolution_minutes: 15, interval_convention: '', units: { pv_ac_kw: 'kW' },
    intervals: [
      { interval_start: '2026-10-21T12:00:00Z', interval_end: '2026-10-21T12:15:00Z', pv_ac_kw: 1000,
        ghi: 500, temp_air_c: 25, wind_speed_ms: 2, cloud_cover_pct: 40,
        arrays: [{ array_id: 4, pv_ac_kw: 900 }] },
    ],
  };

  function renderForecast(selections: string[], aheadHours = 24) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    const rendered = renderHook(() => useHistorianSeries('1001', selections, { preset: '1D' }, { forecastAheadHours: aheadHours }), { wrapper });
    return { ...rendered, queryClient };
  }

  it('fetches every forecast selection once for the window plus the look-ahead, and merges them', async () => {
    const getSeries = vi.spyOn(forecastApi, 'getSeries').mockResolvedValue(FORECAST as never);
    const { result } = renderForecast(['7', 'fc:site:pv_ac_kw', 'fc:4:pv_ac_kw']);

    await waitFor(() => expect(result.current.lines['fc:site:pv_ac_kw']?.length).toBe(2));
    expect(getSeries).toHaveBeenCalledTimes(1);
    const [siteId, start, end] = getSeries.mock.calls[0];
    expect(siteId).toBe('1001');
    expect(Date.parse(end) - Date.parse(start)).toBe(48 * 3_600_000); // 1 day back + 24 h ahead
    expect(result.current.lines['fc:4:pv_ac_kw'].map(point => point['fc:4:pv_ac_kw'])).toEqual([900, 900]);
    expect(result.current.forecastSeries.get('fc:site:pv_ac_kw')?.unit).toBe('kW');
  });

  it('treats "no forecast stored" as no data, and refetches on Refresh', async () => {
    const getSeries = vi.spyOn(forecastApi, 'getSeries').mockRejectedValue({ detail: 'no forecast stored for site 1001 in that window' });
    const { result, queryClient } = renderForecast(['fc:site:pv_ac_kw']);

    await waitFor(() => expect(getSeries).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isError).toBe(false);
    expect(result.current.data).toEqual([]);
    await act(() => queryClient.invalidateQueries({ predicate: isHistorianQueryOf('1001') }));
    await waitFor(() => expect(getSeries).toHaveBeenCalledTimes(2));
  });

  it('does not call the forecast without a forecast selection', async () => {
    const getSeries = vi.spyOn(forecastApi, 'getSeries');
    renderForecast(['7']);
    await waitFor(() => expect(fetches()).toBe(1));
    expect(getSeries).not.toHaveBeenCalled();
  });
});
