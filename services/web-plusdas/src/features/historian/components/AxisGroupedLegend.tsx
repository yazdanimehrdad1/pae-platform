import type { Props as LegendContentProps } from "recharts/types/component/DefaultLegendContent";
import { groupByAxis, type ChartAxis } from "../lib/axes";
import { DASH_ARRAY, type ResolvedStyle } from "../lib/seriesStyles";

interface AxisGroupedLegendProps extends LegendContentProps {
  axes: ChartAxis[];
  axisOf: Map<string, string>;
  /** Called with the clicked entry's data key. */
  onSelect: (dataKey: string) => void;
  /** The line style drawn for an entry's data key (undefined: a solid 2 px line). */
  styleOf: (dataKey: string) => ResolvedStyle | undefined;
}

// The entry's line as drawn, so a dotted or thin line reads as such in the legend too.
function LineSwatch({ color, style }: { color?: string; style?: ResolvedStyle }) {
  return (
    <svg width="14" height="6" aria-hidden className="shrink-0">
      <line x1="0" y1="3" x2="14" y2="3" stroke={color} strokeWidth={style?.width ?? 2} strokeDasharray={style ? DASH_ARRAY[style.dash] : undefined} />
    </svg>
  );
}

// Per unit, the axes show only their unit, so the legend says which points each one carries: one row
// per axis, headed by its unit and side in the axis colour, then every point name in full.
export function AxisGroupedLegend({ payload = [], axes, axisOf, onSelect, styleOf }: AxisGroupedLegendProps) {
  const groups = groupByAxis(payload, entry => String(entry.dataKey), axes, axisOf);
  return (
    <div className="space-y-1 pt-5 text-xs">
      {groups.map(({ axis, entries }) => (
        <div key={axis?.id ?? "unassigned"} className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {axis && (
            <span className="inline-flex min-w-28 items-center gap-1.5 font-medium" style={{ color: axis.color }}>
              <span className="h-3.5 w-[3px] rounded-sm" style={{ backgroundColor: axis.color }} />
              {axis.label || "No unit"} ({axis.side})
            </span>
          )}
          {entries.map(entry => (
            <button
              key={String(entry.dataKey)}
              type="button"
              title="Show in Trends panel"
              className="inline-flex items-center gap-1.5 rounded-sm hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
              onMouseDown={event => event.stopPropagation()}
              onClick={() => onSelect(String(entry.dataKey))}
            >
              <LineSwatch color={entry.color} style={styleOf(String(entry.dataKey))} />
              {String(entry.value).replace(" - ", "-")}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
