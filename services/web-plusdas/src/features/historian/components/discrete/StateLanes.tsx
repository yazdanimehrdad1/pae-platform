import type { ChartRow } from "../../types";
import { stateLabel, type DiscreteSeries } from "../../lib/discreteSeries";
import { toStateSegments } from "./stateSegments";

// Discrete-trend renderer: one lane per enum point or bitfield bit, under the analog chart and
// sharing its time domain. Enum lanes show a coloured run per state, bit lanes are filled while on.
const ENUM_STATE_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#06B6D4", "#EC4899", "#84CC16"];
const TIME_TICK_COUNT = 5;

export function StateLanes({ series, rows, domain, plotLeft, plotRight, formatTime, showTimeAxis, onLaneNameClick }: {
  series: DiscreteSeries[];
  rows: ChartRow[];
  domain: [number, number];
  plotLeft: number;
  plotRight: number;
  formatTime: (timestamp: number) => string;
  // Drawn when there is no analog chart above to carry the time axis.
  showTimeAxis: boolean;
  onLaneNameClick?: (selectionId: string) => void;
}) {
  const [domainStart, domainEnd] = domain;
  const span = Math.max(domainEnd - domainStart, 1);
  const toPercent = (timestamp: number) => ((timestamp - domainStart) / span) * 100;

  const segmentColor = (lane: DiscreteSeries, value: number) => {
    if (lane.kind === "bit") return value === 1 ? lane.color : "transparent";
    const stateIndex = lane.states.findIndex(state => state.value === value);
    return ENUM_STATE_COLORS[stateIndex % ENUM_STATE_COLORS.length] ?? "hsl(var(--muted-foreground))";
  };

  return (
    <div className="space-y-1.5" style={{ paddingLeft: plotLeft, paddingRight: plotRight }} data-testid="state-lanes">
      {series.map(lane => (
        <div key={lane.key}>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: lane.color }} />
            <button type="button" className="truncate hover:text-foreground hover:underline" title="Show in Trends panel"
              onMouseDown={event => event.stopPropagation()} onClick={() => onLaneNameClick?.(lane.key)}>
              {lane.name}
            </button>
          </div>
          <div className="relative h-5 overflow-hidden rounded-sm bg-muted/40">
            {toStateSegments(rows, lane.key, domain).map(segment => {
              const label = stateLabel(lane, segment.value);
              const width = toPercent(segment.end) - toPercent(segment.start);
              return (
                <div
                  key={segment.start}
                  className="absolute inset-y-0 flex items-center overflow-hidden border-r border-background/60 px-1 text-[10px] font-medium text-white"
                  style={{ left: `${toPercent(segment.start)}%`, width: `${width}%`, backgroundColor: segmentColor(lane, segment.value) }}
                  title={`${label} · ${formatTime(segment.start)} – ${formatTime(segment.end)}`}
                >
                  {lane.kind === "enum" && width > 8 && <span className="truncate">{label}</span>}
                </div>
              );
            })}
          </div>
        </div>
      ))}
      {showTimeAxis && (
        <div className="relative h-4 text-[11px] text-muted-foreground">
          {Array.from({ length: TIME_TICK_COUNT }, (_, index) => {
            const fraction = index / (TIME_TICK_COUNT - 1);
            return (
              <span key={index} className="absolute -translate-x-1/2 whitespace-nowrap first:translate-x-0 last:-translate-x-full" style={{ left: `${fraction * 100}%` }}>
                {formatTime(domainStart + fraction * span)}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
