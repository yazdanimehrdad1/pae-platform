import { useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { historianApi } from '@/api/historian';
import { siteFunctionsApi } from '@/api/siteFunctions';
import type { BackendPointReadings, PointTimeseries } from '@/api/types/historian';
import { parseFunctionSelectionId, parseSelectionId, type FunctionSelection } from '@/shared/lib/discretePoints';
import type { ChartRow, TimeWindow } from '../types';
import { buildChartRows, type SeriesByKey } from '../lib/chartRows';
import { usePointCatalog } from './usePointCatalog';

const windowKey = (timeWindow: TimeWindow) => 'preset' in timeWindow
  ? ['preset', timeWindow.preset]
  : ['custom', timeWindow.startTime, timeWindow.endTime];

const windowArgs = (timeWindow: TimeWindow) => 'preset' in timeWindow
  ? { timeRange: timeWindow.preset }
  : { startTime: timeWindow.startTime, endTime: timeWindow.endTime };

export function useHistorianSeries(
  siteId: string | null,
  selectedPoints: string[],
  timeWindow: TimeWindow
): { data: ChartRow[]; functionSeries: Map<string, PointTimeseries>; isLoading: boolean; isError: boolean } {
  const { pointsById, isLoading: devicesLoading } = usePointCatalog(siteId);

  // Profile-function selections, each fetched on its own; the rest are points.
  const functionSelections = useMemo(() => selectedPoints
    .map(selectionId => ({ selectionId, selection: parseFunctionSelectionId(selectionId) }))
    .filter((entry): entry is { selectionId: string; selection: FunctionSelection } => entry.selection !== null),
  [selectedPoints]);

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
  const pointResults = useQueries({
    queries: groups.map(([deviceId, points]) => ({
      queryKey: ['historian-series', siteId, deviceId, points.join(','), ...windowKey(timeWindow)],
      queryFn: () => historianApi.getDevicePointReadings({ siteId: siteId!, deviceId, pointIds: points, ...windowArgs(timeWindow) }),
      enabled: !!siteId && points.length > 0,
      staleTime: 0,
      refetchInterval: 60_000,
    })),
  });

  // One API call per function (a function returning several series is fetched once per selection).
  const functionResults = useQueries({
    queries: functionSelections.map(({ selection }) => ({
      queryKey: ['historian-fn', siteId, selection.deviceId ?? null, selection.name, ...windowKey(timeWindow)],
      queryFn: () => siteFunctionsApi.getSeries({ siteId: siteId!, name: selection.name, deviceId: selection.deviceId, ...windowArgs(timeWindow) }),
      enabled: !!siteId,
      staleTime: 0,
      refetchInterval: 60_000,
    })),
  });

  const results = [...pointResults, ...functionResults];
  const isLoading = devicesLoading || results.some(r => r.isLoading);
  const isError = results.some(r => r.isError);

  const functionSeries = new Map<string, PointTimeseries>();
  functionSelections.forEach(({ selectionId, selection }, index) => {
    const series = functionResults[index]?.data?.[selection.seriesIndex];
    if (series) functionSeries.set(selectionId, series);
  });

  const seriesMaps: SeriesByKey[] = [
    ...pointResults.map(result => (result.data as BackendPointReadings | undefined)?.readings).filter(Boolean),
    Object.fromEntries(functionSeries),
  ];
  const data = buildChartRows(seriesMaps, selectedPoints);

  return { data, functionSeries, isLoading, isError };
}
