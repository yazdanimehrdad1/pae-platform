import { useMemo } from 'react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import { historianApi } from '@/api/historian';
import type { BackendPointReadings, TimeRange } from '@/shared/types/api';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ChartRow = Record<string, any>;

export type TimeWindow =
  | { preset: TimeRange }
  | { startTime: string; endTime: string };

export function useHistorianSeries(
  siteId: string | null,
  selectedPoints: string[],
  timeWindow: TimeWindow
): { data: ChartRow[]; isLoading: boolean; isError: boolean } {
  // Reuse the cache populated by AssetTree — no extra network call
  const { data: deviceEntries = [], isLoading: devicesLoading } = useQuery({
    queryKey: ['site-devices-with-points', siteId],
    queryFn: () => devicesApi.getBySiteWithPoints(siteId!),
    enabled: !!siteId,
  });

  // Group selected point IDs by the device that owns them
  const groups = useMemo(() => {
    const pointDeviceMap: Record<string, string> = {};
    for (const device of deviceEntries) {
      for (const point of device.points) {
        pointDeviceMap[String(point.id)] = String(device.deviceId);
      }
    }
    const byDevice: Record<string, string[]> = {};
    for (const pointId of selectedPoints) {
      const deviceId = pointDeviceMap[pointId];
      if (!deviceId) continue;
      if (!byDevice[deviceId]) byDevice[deviceId] = [];
      byDevice[deviceId].push(pointId);
    }
    return Object.entries(byDevice);
  }, [deviceEntries, selectedPoints]);

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

  // Merge per-point readings into per-timestamp rows for Recharts
  const map = new Map<number, ChartRow>();
  for (const result of queryResults) {
    if (!result.data) continue;
    const response = result.data as BackendPointReadings;
    for (const [pointId, pointData] of Object.entries(response.readings)) {
      for (const entry of pointData.timeseries) {
        if (entry.value == null) continue;
        const timestamp = new Date(entry.time).getTime();
        const row: ChartRow = map.get(timestamp) ?? { timestamp };
        row[pointId] = entry.value;
        map.set(timestamp, row);
      }
    }
  }

  const data = [...map.values()].sort((a, b) => a.timestamp - b.timestamp);

  return { data, isLoading, isError };
}
