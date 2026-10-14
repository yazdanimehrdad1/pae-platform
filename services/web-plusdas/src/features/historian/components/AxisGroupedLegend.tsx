import type { Props as LegendContentProps } from "recharts/types/component/DefaultLegendContent";
import { groupByAxis, type ChartAxis } from "../lib/axes";

interface AxisGroupedLegendProps extends LegendContentProps {
  axes: ChartAxis[];
  axisOf: Map<string, string>;
  /** Called with the clicked entry's data key. */
  onSelect: (dataKey: string) => void;
}

// Per unit, the axes show only their unit, so the legend says which points each one carries: one row
// per axis, headed by its unit and side in the axis colour, then every point name in full.
export function AxisGroupedLegend({ payload = [], axes, axisOf, onSelect }: AxisGroupedLegendProps) {
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
              <span className="h-0.5 w-3.5 rounded-full" style={{ backgroundColor: entry.color }} />
              {String(entry.value).replace(" - ", "-")}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
