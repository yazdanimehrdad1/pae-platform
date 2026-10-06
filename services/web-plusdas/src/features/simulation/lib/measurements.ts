import type { DeviceHistory, DeviceKind, DeviceReadings, PointReading } from '@/api/types/powerflow';

// Pure helpers for the Measurements tab: device names, value formatting and chart rows.

export const DEVICE_KIND_LABELS: Record<DeviceKind, string> = {
  site: 'Site (plant controller)',
  met_station: 'Met station',
  bess: 'BESS',
  pv: 'PV inverter',
  load: 'Load',
  poi_meter: 'POI meter',
  feeder_meter: 'Feeder meter',
};

export const deviceKey = (device: Pick<DeviceReadings, 'kind' | 'asset_id'>) => `${device.kind}.${device.asset_id}`;

export function deviceName(device: Pick<DeviceReadings, 'kind' | 'asset_id'>): string {
  const kind = DEVICE_KIND_LABELS[device.kind];
  return device.kind === 'site' || device.kind === 'poi_meter' || device.kind === 'met_station'
    ? kind
    : `${kind} ${device.asset_id}`;
}

/** A point is chartable when it's a served number (not an enum or a bitfield). */
export function isTrendable(point: PointReading): boolean {
  return point.served !== 'no' && !point.data_type.startsWith('enum') && !point.data_type.startsWith('bitfield');
}

/** The value as shown: enum/bit labels for codes, a number with its unit otherwise. */
export function formatReading(point: PointReading): string {
  if (point.value == null) return '–';
  if (point.text != null) {
    const code = Number.isInteger(point.value) ? point.value : Math.round(point.value);
    return point.text === '' ? `${code} (none)` : `${point.text} (${code})`;
  }
  const number = Math.abs(point.value) >= 1000 ? Math.round(point.value) : Number(point.value.toPrecision(4));
  return `${number.toLocaleString(undefined, { maximumFractionDigits: 6 })}${point.unit ? ` ${point.unit}` : ''}`;
}

/** Points matching a filter (name or label, case-insensitive), optionally without unserved ones. */
export function filterPoints(points: PointReading[], query: string, showUnserved: boolean): PointReading[] {
  const needle = query.trim().toLowerCase();
  return points.filter(
    (point) =>
      (showUnserved || point.served !== 'no') &&
      (!needle || point.point.toLowerCase().includes(needle) || point.label.toLowerCase().includes(needle)),
  );
}

export type TrendRow = { t: number; step: number } & Record<string, number | null>;

/** recharts rows: one per sample, keyed by point name (null = no value, a gap). */
export function trendRows(history: DeviceHistory): TrendRow[] {
  return history.samples.map((sample) => {
    const row: TrendRow = { t: Date.parse(sample.sim_time), step: sample.step_id };
    history.points.forEach((point, index) => {
      row[point.point] = sample.values[index] ?? null;
    });
    return row;
  });
}
