import type { BackendPointReadings } from '@/api/types/historian';
import { decodeBit, parseSelectionId } from '@/shared/lib/discretePoints';
import type { ChartRow } from '../types';

// Merges per-point readings into per-timestamp rows for Recharts, one column per selection.
// A bit selection ("12:bit3") gets that bit (0/1) of point 12's raw value; others get the value.
export function buildChartRows(responses: BackendPointReadings[], selectionIds: string[]): ChartRow[] {
  const selectionsByPoint = new Map<string, Array<{ selectionId: string; bit?: number }>>();
  for (const selectionId of selectionIds) {
    const { pointId, bit } = parseSelectionId(selectionId);
    selectionsByPoint.set(pointId, [...(selectionsByPoint.get(pointId) ?? []), { selectionId, bit }]);
  }

  const rowsByTimestamp = new Map<number, ChartRow>();
  for (const response of responses) {
    for (const [pointId, pointData] of Object.entries(response.readings)) {
      const selections = selectionsByPoint.get(pointId) ?? [];
      for (const entry of pointData.timeseries) {
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
