import type { PointTimeseries } from '@/api/types/historian';
import { decodeBit, parseSelectionId } from '@/shared/lib/discretePoints';
import type { ChartRow } from '../types';

// Series by key: a readings response's `readings` (keyed by point id), or a profile function's
// series keyed by its selection id ("fn:...").
export type SeriesByKey = Record<string, PointTimeseries>;

// Devices are polled a moment apart, so one poll cycle's readings carry timestamps a few ms
// apart. Readings within this of a row's first one share that row (backend-ot lines up series
// with the same tolerance, ALIGN_TOLERANCE in helpers/common/series_alignment.py).
export const ROW_TOLERANCE_MS = 1000;

interface Reading {
  timestamp: number;
  key: string;
  value: number;
}

// Merges fetched series into rows for Recharts, one column per selection, each series at its own
// sample times (no resampling): one poll cycle across devices is one row, stamped with its last
// reading's time. A series sampled twice within the tolerance gets two rows, and a series with no
// reading in a row leaves its column empty, so an outage still shows as a gap.
// A bit selection ("12:bit3") gets that bit (0/1) of point 12's raw value; others get the value.
export function buildChartRows(seriesMaps: SeriesByKey[], selectionIds: string[]): ChartRow[] {
  const selectionsByKey = new Map<string, Array<{ selectionId: string; bit?: number }>>();
  for (const selectionId of selectionIds) {
    const { pointId, bit } = parseSelectionId(selectionId);
    selectionsByKey.set(pointId, [...(selectionsByKey.get(pointId) ?? []), { selectionId, bit }]);
  }

  const readings: Reading[] = [];
  for (const seriesByKey of seriesMaps) {
    for (const [key, series] of Object.entries(seriesByKey)) {
      if (!selectionsByKey.has(key)) continue;
      for (const entry of series.timeseries) {
        if (entry.value == null) continue;
        readings.push({ timestamp: new Date(entry.time).getTime(), key, value: entry.value });
      }
    }
  }
  readings.sort((left, right) => left.timestamp - right.timestamp);

  const rows: ChartRow[] = [];
  let row: ChartRow | null = null;
  let rowStart = 0;
  let keysInRow = new Set<string>();
  for (const { timestamp, key, value } of readings) {
    if (!row || timestamp - rowStart >= ROW_TOLERANCE_MS || keysInRow.has(key)) {
      row = { timestamp };
      rows.push(row);
      rowStart = timestamp;
      keysInRow = new Set();
    }
    row.timestamp = timestamp;
    keysInRow.add(key);
    for (const { selectionId, bit } of selectionsByKey.get(key)!) {
      row[selectionId] = bit === undefined ? value : decodeBit(value, bit);
    }
  }
  return rows;
}
