import { useMemo } from 'react';
import { keepPreviousData, useQueries, useQuery } from '@tanstack/react-query';
import { forecastApi, toForecastSeries } from '@/api/forecast';
import { historianApi } from '@/api/historian';
import { siteFunctionsApi } from '@/api/siteFunctions';
import type { BackendPointReadings, PointTimeseries } from '@/api/types/historian';
import {
  parseForecastSelectionId, parseFunctionSelectionId, parseSelectionId, type FunctionSelection,
} from '@/shared/lib/discretePoints';
import type { ChartRow, TimeWindow } from '../types';
import { buildChartRows, buildLineSeries, type LinePoint, type SeriesByKey } from '../sampling/chartRows';
import { PLOT_POINTS } from '../sampling/constants';
import { usePointCatalog } from './usePointCatalog';
import { forecastRange } from '../lib/timeWindows';

// Readings are fetched when a chart needs them (a new point, window or zoom), and again only when
// the user asks: the Refresh button, or Auto refresh (off by default) every AUTO_REFRESH_MS. So no
// refetch on a timer, on window focus, on reconnect or when a chart remounts.
export const AUTO_REFRESH_MS = 60_000;
const SERIES_KEY = 'historian-series';
const FUNCTION_KEY = 'historian-fn';
const FORECAST_KEY = 'historian-forecast';
const HISTORIAN_KEYS: readonly unknown[] = [SERIES_KEY, FUNCTION_KEY, FORECAST_KEY];

/** Every readings query of the site's charts (points, site functions, the PV forecast): what
 * Refresh refetches. */
export function isHistorianQueryOf(siteId: string | null) {
  return (query: { queryKey: readonly unknown[] }) =>
    HISTORIAN_KEYS.includes(query.queryKey[0]) && query.queryKey[1] === siteId;
}

// "Not found" from intelli-gateway: no forecast stored for that window yet, i.e. no data.
function isNotFound(error: unknown): boolean {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === 'string' && detail.startsWith('no forecast');
}

const fetchOnRequestOnly = (autoRefresh: boolean) => ({
  staleTime: Infinity,
  refetchInterval: autoRefresh ? AUTO_REFRESH_MS : false,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
} as const);

const windowKey = (timeWindow: TimeWindow) => 'preset' in timeWindow
  ? ['preset', timeWindow.preset]
  : ['custom', timeWindow.startTime, timeWindow.endTime];

// Every request is a chart's (max_points): every reading up to 3 days, plot values beyond.
const windowArgs = (timeWindow: TimeWindow) => ({
  maxPoints: PLOT_POINTS,
  ...('preset' in timeWindow ? { timeRange: timeWindow.preset } : { startTime: timeWindow.startTime, endTime: timeWindow.endTime }),
});

// `timeWindow` is what the chart shows: the selected window, or the zoomed range (so zooming in
// refetches, and a zoom of 3 days or less gets every reading). While a new window loads, the
// previous data stays on screen.
export function useHistorianSeries(
  siteId: string | null,
  selectedPoints: string[],
  timeWindow: TimeWindow,
  { autoRefresh = false, forecastAheadHours = 0 }: { autoRefresh?: boolean; forecastAheadHours?: number } = {},
): {
  data: ChartRow[];
  lines: Record<string, LinePoint[]>;
  functionSeries: Map<string, PointTimeseries>;
  forecastSeries: Map<string, PointTimeseries>;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
} {
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
      queryKey: [SERIES_KEY, siteId, deviceId, points.join(','), ...windowKey(timeWindow)],
      queryFn: () => historianApi.getDevicePointReadings({ siteId: siteId!, deviceId, pointIds: points, ...windowArgs(timeWindow) }),
      enabled: !!siteId && points.length > 0,
      ...fetchOnRequestOnly(autoRefresh),
      placeholderData: keepPreviousData,
    })),
  });

  // One API call per function (a function returning several series is fetched once per selection).
  const functionResults = useQueries({
    queries: functionSelections.map(({ selection }) => ({
      queryKey: [FUNCTION_KEY, siteId, selection.deviceId ?? null, selection.name, ...windowKey(timeWindow)],
      queryFn: () => siteFunctionsApi.getSeries({ siteId: siteId!, name: selection.name, deviceId: selection.deviceId, ...windowArgs(timeWindow) }),
      enabled: !!siteId,
      ...fetchOnRequestOnly(autoRefresh),
      placeholderData: keepPreviousData,
    })),
  });

  // PV forecast selections share one fetch for the chart's window (plus the look-ahead on a
  // preset). The window is resolved when it is fetched, so a refresh moves "now" along.
  const forecastSelections = useMemo(
    () => selectedPoints.filter(selectionId => parseForecastSelectionId(selectionId) !== null),
    [selectedPoints],
  );
  const forecastResult = useQuery({
    queryKey: [FORECAST_KEY, siteId, ...windowKey(timeWindow), forecastAheadHours],
    queryFn: async () => {
      const { start, end } = forecastRange(timeWindow, forecastAheadHours);
      try {
        return await forecastApi.getSeries(siteId!, start, end);
      } catch (error) {
        if (isNotFound(error)) return null;
        throw error;
      }
    },
    enabled: !!siteId && forecastSelections.length > 0,
    ...fetchOnRequestOnly(autoRefresh),
    placeholderData: keepPreviousData,
  });

  const results = [...pointResults, ...functionResults, ...(forecastSelections.length > 0 ? [forecastResult] : [])];
  const isLoading = devicesLoading || results.some(r => r.isLoading);
  const isFetching = results.some(r => r.isFetching);
  const isError = results.some(r => r.isError);

  // Rebuilt only when a fetch returns or the selection changes: a 3-day window is ~26k readings
  // per point, too many to merge on every render.
  const dataVersion = results.map(result => result.dataUpdatedAt).join(',');
  const { data, lines, functionSeries, forecastSeries } = useMemo(() => {
    const seriesByFunction = new Map<string, PointTimeseries>();
    functionSelections.forEach(({ selectionId, selection }, index) => {
      const series = functionResults[index]?.data?.[selection.seriesIndex];
      if (series) seriesByFunction.set(selectionId, series);
    });
    const seriesByForecast = forecastResult.data && forecastSelections.length > 0
      ? toForecastSeries(forecastResult.data, forecastSelections)
      : {};
    const seriesMaps: SeriesByKey[] = [
      ...pointResults.map(result => (result.data as BackendPointReadings | undefined)?.readings).filter(Boolean),
      Object.fromEntries(seriesByFunction),
      seriesByForecast,
    ];
    return {
      data: buildChartRows(seriesMaps, selectedPoints),
      lines: buildLineSeries(seriesMaps, selectedPoints),
      functionSeries: seriesByFunction,
      forecastSeries: new Map(Object.entries(seriesByForecast)),
    };
    // Keyed on dataVersion: the query result arrays are new objects on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataVersion, selectedPoints, functionSelections, forecastSelections]);

  return { data, lines, functionSeries, forecastSeries, isLoading, isFetching, isError };
}
