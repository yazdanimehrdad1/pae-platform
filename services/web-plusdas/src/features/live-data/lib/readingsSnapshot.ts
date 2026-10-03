import type { DevicePoint } from "@/api/types/devicePoints";
import { POINT_GROUP_ORDER, type DevicePointsEntry, type PointGroup } from "@/api/types/devices";
import type { BackendPointReadings } from "@/api/types/historian";
import { decodeBit, decodeEnum, isBitfieldPoint, isEnumPoint, sortedBits } from "@/shared/lib/discretePoints";

// A device's readings snapshot as a table: one row per point (grouped standardized, virtual,
// native), one column per recent poll time. A device's points are polled together, and virtual
// points are computed at their inputs' times, so readings of one poll share a column. Times are
// keyed to the second so small timestamp differences within a poll still line up.

export const SNAPSHOT_READINGS = 10;

export interface SnapshotColumn {
  /** Whole seconds since the epoch. */
  key: number;
  /** The column's time (the newest reading in that second), ISO. */
  time: string;
}

export interface SnapshotRow {
  point: DevicePoint;
  /** The point's value in each column, null when it has no reading then. */
  cells: (number | null)[];
}

export interface SnapshotTable {
  columns: SnapshotColumn[];
  groups: { group: PointGroup; rows: SnapshotRow[] }[];
}

const secondKey = (time: string) => Math.floor(Date.parse(time) / 1000);

export function buildReadingsTable(device: DevicePointsEntry, readings: BackendPointReadings, columnCount = SNAPSHOT_READINGS): SnapshotTable {
  // The value of each point at each second (the newest reading in that second wins).
  const valuesByPoint = new Map<string, Map<number, number>>();
  const timeByKey = new Map<number, string>();
  for (const [pointId, series] of Object.entries(readings.readings)) {
    const values = new Map<number, number>();
    for (const reading of series.timeseries ?? []) {
      if (reading.value == null) continue;
      const key = secondKey(reading.time);
      if (!values.has(key)) values.set(key, reading.value);
      const known = timeByKey.get(key);
      if (!known || Date.parse(reading.time) > Date.parse(known)) timeByKey.set(key, reading.time);
    }
    valuesByPoint.set(pointId, values);
  }

  const columns = [...timeByKey.entries()]
    .sort(([left], [right]) => right - left)
    .slice(0, columnCount)
    .map(([key, time]) => ({ key, time }));

  const groups = POINT_GROUP_ORDER
    .map(group => ({
      group,
      rows: device.groups[group].map(point => {
        const values = valuesByPoint.get(String(point.id));
        return { point, cells: columns.map(column => values?.get(column.key) ?? null) };
      }),
    }))
    .filter(entry => entry.rows.length > 0);

  return { columns, groups };
}

/** A cell as text: an enum's state label, a bitfield in hex (its set bits as the title), else the number. */
export function formatReading(point: DevicePoint, value: number | null): { text: string; title?: string } {
  if (value === null) return { text: "—" };
  if (isEnumPoint(point)) return { text: decodeEnum(value, point.enum_detail), title: String(value) };
  if (isBitfieldPoint(point)) {
    const setBits = sortedBits(point.bitfield_detail).filter(definition => decodeBit(value, definition.bit) === 1);
    return {
      text: `0x${Math.round(value).toString(16).toUpperCase()}`,
      title: setBits.length ? setBits.map(definition => `${definition.bit}: ${definition.label}`).join(", ") : "no labelled bit set",
    };
  }
  return { text: String(Number(value.toPrecision(10))) };
}
