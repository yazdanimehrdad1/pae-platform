// Which vertical axis each analog line of a trend chart is drawn against. One shared axis squashes
// a 1-10 signal into a flat line next to a 1000-5000 one, so by default every unit gets its own
// axis; "per point" separates lines of one unit but very different size; "shared" is one axis.

export type AxisScale = "per-unit" | "per-point" | "shared";

export const AXIS_SCALE_LABELS: Record<AxisScale, string> = {
  "per-unit": "Per unit",
  "per-point": "Per point",
  shared: "Shared",
};

export const DEFAULT_AXIS_SCALE: AxisScale = "per-unit";

/** Per unit, the axes take neutral colours in turn (they carry several lines, so a line colour would
 * mislead): black, grey, dark blue; on the dark theme their light counterparts, so they stay readable. */
export const UNIT_AXIS_COLORS = {
  light: ["#111827", "#6b7280", "#1e3a8a"],
  dark: ["#f3f4f6", "#9ca3af", "#60a5fa"],
} as const;

export function isAxisScale(value: unknown): value is AxisScale {
  return typeof value === "string" && value in AXIS_SCALE_LABELS;
}

export interface ChartAxis {
  id: string;
  side: "left" | "right";
  /** Per unit: its unit ("" for points without one); per point: the point's name (and unit); shared:
   * the unit when all lines share one, else "". */
  label: string;
  /** The names of the points drawn against it, in `keys` order. */
  names: string[];
  /** Per unit: a neutral colour (UNIT_AXIS_COLORS); per point: its line's colour; shared: undefined. */
  color?: string;
  keys: string[];
}

export interface AxisLine {
  key: string;
  unit: string | null;
  label: string;
  color?: string;
}

/** Axes in order (alternating left, right, left...) and each line's axis id. `unitColors` are the
 * per-unit axis colours, used in turn. */
export function assignAxes(
  lines: AxisLine[],
  scale: AxisScale,
  unitColors: readonly string[] = UNIT_AXIS_COLORS.light,
): { axes: ChartAxis[]; axisOf: Map<string, string> } {
  const groups: { label: string; keys: string[]; names: string[]; color?: string }[] = [];
  if (scale === "shared") {
    const units = new Set(lines.map(line => line.unit ?? ""));
    if (lines.length > 0) {
      groups.push({ label: units.size === 1 ? [...units][0] : "", keys: lines.map(line => line.key), names: lines.map(line => line.label) });
    }
  } else if (scale === "per-point") {
    for (const line of lines) {
      groups.push({ label: line.unit ? `${line.label} (${line.unit})` : line.label, keys: [line.key], names: [line.label], color: line.color });
    }
  } else {
    const byUnit = new Map<string, { names: string[]; keys: string[] }>();
    for (const line of lines) {
      const unit = line.unit ?? "";
      const group = byUnit.get(unit) ?? { names: [], keys: [] };
      group.keys.push(line.key);
      group.names.push(line.label);
      byUnit.set(unit, group);
    }
    [...byUnit.entries()].forEach(([unit, group], index) => groups.push({
      label: unit,
      keys: group.keys,
      names: group.names,
      color: unitColors[index % unitColors.length],
    }));
  }

  // Per point colours each axis like its line; a single shared axis stays neutral.
  const neutral = scale === "shared";
  const axes = groups.map((group, index): ChartAxis => ({
    id: `axis-${index}`,
    side: index % 2 === 0 ? "left" : "right",
    label: group.label,
    names: group.names,
    color: neutral ? undefined : group.color,
    keys: group.keys,
  }));
  const axisOf = new Map(axes.flatMap(axis => axis.keys.map(key => [key, axis.id] as const)));
  return { axes, axisOf };
}

// Each axis is only as wide as its numbers (plus its label, if any), so a label sits right next to
// its ticks instead of at the far edge of a fixed-width box, and the plot keeps the rest.
const CHAR_PX = 7; // a digit at the ticks' 12 px font
const TICK_PX = 10; // the tick mark and the gap to its number
const LABEL_PX = 16; // a rotated 11 px label
const MIN_NUMBERS_PX = 21; // three digits: room for the ticks before any data arrives

/** The tick text a value turns into, about. Recharts picks about five "nice" ticks, so a span of 4
 * or more gets whole numbers (0-10 shows 0, 3, 6, 9...), under 4 one decimal, under 0.4 two. */
function tickText(value: number, span: number): string {
  const decimals = span < 0.4 ? 2 : span < 4 ? 1 : 0;
  return value.toFixed(decimals);
}

/** Width in px of an axis whose lines span `range` (null before data arrives). */
export function axisWidth(range: { min: number; max: number } | null, hasLabel: boolean): number {
  const span = range ? range.max - range.min : 0;
  // The top tick can round up past the data to the next power of ten (9 800 shows a 10 000 tick).
  const top = (value: number) => {
    const magnitude = Math.abs(value);
    const nextPower = magnitude >= 1 ? 10 ** Math.ceil(Math.log10(magnitude)) : 1;
    return magnitude >= 0.8 * nextPower ? Math.sign(value) * nextPower : value;
  };
  const chars = range ? Math.max(tickText(top(range.min), span).length, tickText(top(range.max), span).length) : 3;
  return Math.max(MIN_NUMBERS_PX, chars * CHAR_PX) + TICK_PX + (hasLabel ? LABEL_PX : 0);
}

/** Legend entries grouped by the axis their line is drawn against, in axis order; entries on no axis
 * (the discrete step series) come last under a null axis. Groups without entries are left out. */
export function groupByAxis<Entry>(
  entries: Entry[],
  keyOf: (entry: Entry) => string,
  axes: ChartAxis[],
  axisOf: Map<string, string>,
): { axis: ChartAxis | null; entries: Entry[] }[] {
  const groups = [...axes, null].map(axis => ({ axis, entries: [] as Entry[] }));
  const groupOf = new Map(groups.filter(group => group.axis).map(group => [group.axis.id, group]));
  const unassigned = groups[groups.length - 1];
  for (const entry of entries) (groupOf.get(axisOf.get(keyOf(entry))) ?? unassigned).entries.push(entry);
  return groups.filter(group => group.entries.length > 0);
}

/** The lowest and highest value of the given lines (null when none has a value). */
export function valueRange(lines: Record<string, Array<Record<string, number | null>>>, keys: string[]): { min: number; max: number } | null {
  let min = Infinity;
  let max = -Infinity;
  for (const key of keys) {
    for (const sample of lines[key] ?? []) {
      const value = sample[key];
      if (typeof value !== "number") continue;
      if (value < min) min = value;
      if (value > max) max = value;
    }
  }
  return min === Infinity ? null : { min, max };
}
