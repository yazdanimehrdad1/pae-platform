import type { PointTimeseries } from '@/api/types/historian';
import { decodeBit, parseSelectionId } from '@/shared/lib/discretePoints';
import type { ChartRow } from '../types';

// Series by key: a readings response's `readings` (keyed by point id), or a profile function's
// series keyed by its selection id ("fn:...").
export type SeriesByKey = Record<string, PointTimeseries>;

// Merges fetched series into per-timestamp rows for Recharts, one column per selection.
// A bit selection ("12:bit3") gets that bit (0/1) of point 12's raw value; others get the value.
export function buildChartRows(seriesMaps: SeriesByKey[], selectionIds: string[]): ChartRow[] {
  const selectionsByKey = new Map<string, Array<{ selectionId: string; bit?: number }>>();
  for (const selectionId of selectionIds) {
    const { pointId, bit } = parseSelectionId(selectionId);
    selectionsByKey.set(pointId, [...(selectionsByKey.get(pointId) ?? []), { selectionId, bit }]);
  }

  const rowsByTimestamp = new Map<number, ChartRow>();
  for (const seriesByKey of seriesMaps) {
    for (const [key, series] of Object.entries(seriesByKey)) {
      const selections = selectionsByKey.get(key) ?? [];
      for (const entry of series.timeseries) {
        if (entry.value == null) continue;
        const timestamp = new Date(entry.time).getTime();
        const row: ChartRow = rowsByTimestamp.get(timestamp) ?? { timestamp };
        for (const { selectionId, bit } of selections) {
          row[selectionId] = bit === undefined ? entry.value : decodeBit(entry.value, bit);
        }
        rowsByTimestamp.set(timestamp, row);
      }
    }
  }

  return [...rowsByTimestamp.values()].sort((left, right) => left.timestamp - right.timestamp);
}
