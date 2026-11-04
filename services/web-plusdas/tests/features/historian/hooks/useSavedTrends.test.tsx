// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { meApi } from '@/api/me';
import type { SavedTrend, TrendDefinition } from '@/api/types/me';
import { useSavedTrends } from '@/features/historian/hooks/useSavedTrends';

const saved = (id: number, name: string, points: string[] = []): SavedTrend => ({
  id, position: id - 1, name, points, scale: null, styles: null,
  created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z',
});

function render(server: SavedTrend[]) {
  vi.spyOn(meApi, 'listTrends').mockResolvedValue(server);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  return renderHook(() => useSavedTrends(), { wrapper });
}

let nextId = 100;
beforeEach(() => {
  vi.spyOn(meApi, 'createTrend').mockImplementation(async (trend: TrendDefinition) => saved(nextId++, trend.name, trend.points ?? []));
  vi.spyOn(meApi, 'updateTrend').mockImplementation(async (id: number, trend: TrendDefinition) => saved(id, trend.name, trend.points ?? []));
  vi.spyOn(meApi, 'deleteTrend').mockResolvedValue(undefined);
  vi.spyOn(meApi, 'reorderTrends').mockResolvedValue([]);
});

afterEach(() => vi.restoreAllMocks());

describe('useSavedTrends', () => {
  it("loads the user's trends", async () => {
    const { result } = render([saved(1, 'BESS', ['101']), saved(2, 'PV')]);
    await waitFor(() => expect(result.current.isLoaded).toBe(true));
    expect(result.current.trends).toEqual([{ id: '1', name: 'BESS', points: ['101'] }, { id: '2', name: 'PV', points: [] }]);
    expect(meApi.createTrend).not.toHaveBeenCalled();
  });

  it('gives a user with no trends one empty Default Trend, saved', async () => {
    const { result } = render([]);
    await waitFor(() => expect(result.current.trends.map(trend => trend.name)).toEqual(['Default Trend']));
    expect(meApi.createTrend).toHaveBeenCalledTimes(1);
  });

  it('saves quick edits to a trend once, with the last state', async () => {
    const { result } = render([saved(1, 'BESS')]);
    await waitFor(() => expect(result.current.isLoaded).toBe(true));
    act(() => result.current.setTrends(trends => trends.map(trend => ({ ...trend, points: ['101'] }))));
    act(() => result.current.setTrends(trends => trends.map(trend => ({ ...trend, points: ['101', '102'] }))));
    await waitFor(() => expect(meApi.updateTrend).toHaveBeenCalledTimes(1));
    expect(meApi.updateTrend).toHaveBeenCalledWith(1, { name: 'BESS', points: ['101', '102'], scale: null, styles: null });
  });

  it('deletes at once and saves the new order', async () => {
    const { result } = render([saved(1, 'A'), saved(2, 'B'), saved(3, 'C')]);
    await waitFor(() => expect(result.current.isLoaded).toBe(true));
    act(() => result.current.setTrends(trends => [trends[2], trends[0]]));
    await waitFor(() => expect(meApi.reorderTrends).toHaveBeenCalledWith([3, 1]));
    expect(meApi.deleteTrend).toHaveBeenCalledWith(2);
    expect(vi.mocked(meApi.deleteTrend).mock.invocationCallOrder[0])
      .toBeLessThan(vi.mocked(meApi.reorderTrends).mock.invocationCallOrder[0]);
    expect(meApi.updateTrend).not.toHaveBeenCalled();
  });

  it('creates a trend on the server first, so it has its real id', async () => {
    const { result } = render([saved(1, 'A')]);
    await waitFor(() => expect(result.current.isLoaded).toBe(true));
    let created: { id: string } | undefined;
    await act(async () => { created = await result.current.createTrend('New'); });
    expect(meApi.createTrend).toHaveBeenCalledWith({ name: 'New', points: [], scale: null, styles: null });
    expect(result.current.trends.map(trend => trend.id)).toEqual(['1', created?.id]);
    expect(meApi.reorderTrends).not.toHaveBeenCalled();
  });

  it('sends an edit still waiting when the page closes', async () => {
    const { result, unmount } = render([saved(1, 'BESS')]);
    await waitFor(() => expect(result.current.isLoaded).toBe(true));
    act(() => result.current.setTrends(trends => trends.map(trend => ({ ...trend, name: 'Renamed' }))));
    unmount();
    await waitFor(() => expect(meApi.updateTrend).toHaveBeenCalledWith(1, { name: 'Renamed', points: [], scale: null, styles: null }));
  });
});
