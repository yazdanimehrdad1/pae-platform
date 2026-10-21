import type { PointTimeseries, TimeseriesPoint } from './types/historian';
import type { ForecastInterval, PvForecastResponse } from './types/forecast';
import { intelliGatewayClient } from './client';
import { parseForecastSelectionId } from '@/shared/lib/discretePoints';

export const forecastApi = {
  /** The as-forecast PV series over [start, end): past intervals as forecast just before they
   * began, future ones the latest forecast (intelli-gateway). `end` may be in the future. */
  getSeries: (siteId: string, start: string, end: string): Promise<PvForecastResponse> => {
    const params = new URLSearchParams({ start, end });
    return intelliGatewayClient.get(`/v1/sites/${siteId}/forecast/series?${params}`);
  },
};

function valueOf(interval: ForecastInterval, variable: string, deviceId?: string): number | null {
  const source = deviceId === undefined
    ? interval
    : interval.arrays.find(array => String(array.array_id) === deviceId);
  const value = source ? (source as unknown as Record<string, unknown>)[variable] : undefined;
  return typeof value === 'number' ? value : null;
}

/** The forecast's series for the given forecast selections, shaped like backend-ot's point
 * series so the Historian merges them like any other. Each 15-minute value is a sample at its
 * interval_start; a last sample at the final interval_end repeats it, so a step line covers the
 * whole last interval. Selections that aren't forecast ids are ignored. */
export function toForecastSeries(
  response: PvForecastResponse,
  selectionIds: string[],
  labels: Record<string, string> = {},
): Record<string, PointTimeseries> {
  const result: Record<string, PointTimeseries> = {};
  for (const selectionId of selectionIds) {
    const selection = parseForecastSelectionId(selectionId);
    if (!selection) continue;
    const samples: TimeseriesPoint[] = [];
    let last: { end: string; value: number } | null = null;
    for (const interval of response.intervals) {
      const value = valueOf(interval, selection.variable, selection.deviceId);
      samples.push({ time: interval.interval_start, value });
      last = value === null ? null : { end: interval.interval_end, value };
    }
    if (last) samples.push({ time: last.end, value: last.value });
    result[selectionId] = {
      id: 0,
      name: labels[selectionId] ?? selectionId,
      data_type: 'float32',
      unit: response.units?.[selection.variable] ?? null,
      count: samples.length,
      timeseries: samples,
    };
  }
  return result;
}
