import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { historianApi } from '@/api/historian';
import type { BackendPointReadings } from '@/api/types/historian';
import { parseSelectionId } from '@/shared/lib/discretePoints';
import type { ChartRow, TimeWindow } from '../types';
import { buildChartRows } from '../lib/chartRows';
import { usePointCatalog } from './usePointCatalog';

export function useHistorianSeries(
  siteId: string | null,
  selectedPoints: string[],
  timeWindow: TimeWindow
): { data: ChartRow[]; isLoading: boolean; isError: boolean } {
  const { pointsById, isLoading: devicesLoading } = usePointCatalog(siteId);

  // Group the underlying point IDs by owning device; bits of one bitfield share a single fetch.
  const groups = useMemo(() => {
    const byDevice: Record<string, string[]> = {};
    for (const selectionId of selectedPoints) {
      const { pointId } = parseSelectionId(selectionId);
      const deviceId = pointsById.get(pointId)?.deviceId;
      if (!deviceId) continue;
      if (!byDevice[deviceId]) byDevice[deviceId] = [];
      if (!byDevice[deviceId].includes(pointId)) byDevice[deviceId].push(pointId);
    }
    return Object.entries(byDevice);
  }, [pointsById, selectedPoints]);

  // One API call per device group, in parallel
  const queryResults = useQueries({
    queries: groups.map(([deviceId, points]) => ({
      queryKey: 'preset' in timeWindow
        ? ['historian-series', siteId, deviceId, points.join(','), 'preset', timeWindow.preset]
        : ['historian-series', siteId, deviceId, points.join(','), 'custom', timeWindow.startTime, timeWindow.endTime],
      queryFn: () => 'preset' in timeWindow
        ? historianApi.getDevicePointReadings({ siteId: siteId!, deviceId, pointIds: points, timeRange: timeWindow.preset })
        : historianApi.getDevicePointReadings({ siteId: siteId!, deviceId, pointIds: points, startTime: timeWindow.startTime, endTime: timeWindow.endTime }),
      enabled: !!siteId && points.length > 0,
      staleTime: 0,
      refetchInterval: 60_000,
    })),
  });

  const isLoading = devicesLoading || queryResults.some(r => r.isLoading);
  const isError = queryResults.some(r => r.isError);

  const responses = queryResults.map(result => result.data as BackendPointReadings | undefined).filter(Boolean);
  const data = buildChartRows(responses, selectedPoints);

  return { data, isLoading, isError };
}
