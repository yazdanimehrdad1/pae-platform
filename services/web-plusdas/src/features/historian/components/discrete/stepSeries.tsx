import { Line, YAxis } from "recharts";
import type { ChartRow } from "../../types";
import { stateLabel, type DiscreteSeries } from "../../lib/discreteSeries";

// Discrete-trend renderer: enum points and bitfield bits as step lines on the main chart, on a
// right-hand state axis. Each series gets its own band of levels (one level per state) stacked
// bottom-up, so several status points stay readable. Rows get a plotted value per series under
// `plotKey(key)`, and the tooltip maps it back to the state label.
//
// Returns chart children instead of being a component: Recharts 2 only sees direct children.
export const STATE_AXIS_ID = "state";
export const STATE_AXIS_WIDTH = 120;
const BAND_GAP = 1.5;

const plotKey = (key: string) => `step:${key}`;

interface Band {
  series: DiscreteSeries;
  offset: number;
}

export interface StepLayout {
  bands: Band[];
  addPlotValues: (rows: ChartRow[]) => ChartRow[];
  // The state label for a plotted tooltip value, or undefined when the entry isn't a step series.
  tooltipLabel: (dataKey: unknown, plottedValue: number) => string | undefined;
  // The selection id a plotted line stands for, or undefined when it isn't a step series.
  selectionKey: (dataKey: unknown) => string | undefined;
}

export function buildStepLayout(series: DiscreteSeries[]): StepLayout {
  let offset = 0;
  const bands = series.map(entry => {
    const band = { series: entry, offset };
    offset += entry.states.length - 1 + BAND_GAP;
    return band;
  });
  const bandsByPlotKey = new Map(bands.map(band => [plotKey(band.series.key), band]));

  return {
    bands,
    addPlotValues: rows => rows.map(row => {
      const plotted: ChartRow = { ...row };
      for (const { series: entry, offset: bandOffset } of bands) {
        if (row[entry.key] == null) continue;
        const stateIndex = entry.states.findIndex(state => state.value === Math.round(row[entry.key]));
        if (stateIndex >= 0) plotted[plotKey(entry.key)] = bandOffset + stateIndex;
      }
      return plotted;
    }),
    selectionKey: dataKey => (typeof dataKey === "string" ? bandsByPlotKey.get(dataKey)?.series.key : undefined),
    tooltipLabel: (dataKey, plottedValue) => {
      const band = typeof dataKey === "string" ? bandsByPlotKey.get(dataKey) : undefined;
      if (!band) return undefined;
      const state = band.series.states[Math.round(plottedValue - band.offset)];
      return state ? stateLabel(band.series, state.value) : undefined;
    },
  };
}

export function renderStepSeries(layout: StepLayout) {
  const ticks: number[] = [];
  const tickLabels = new Map<number, string>();
  for (const { series: entry, offset } of layout.bands) {
    entry.states.forEach((state, stateIndex) => {
      // A bit's "on" level carries its name; its "off" level stays unlabelled.
      const label = entry.kind === "bit" ? (state.value === 1 ? entry.name : "") : state.label;
      ticks.push(offset + stateIndex);
      tickLabels.set(offset + stateIndex, label);
    });
  }
  const top = ticks.length ? Math.max(...ticks) : 1;

  return [
    <YAxis
      key="state-axis"
      yAxisId={STATE_AXIS_ID}
      orientation="right"
      width={STATE_AXIS_WIDTH}
      domain={[-0.5, top + 0.5]}
      ticks={ticks}
      interval={0}
      tick={{ fontSize: 11 }}
      tickFormatter={(value: number) => {
        const label = tickLabels.get(value) ?? "";
        return label.length > 18 ? `${label.slice(0, 17)}…` : label;
      }}
    />,
    ...layout.bands.map(({ series: entry }) => (
      <Line
        key={plotKey(entry.key)}
        yAxisId={STATE_AXIS_ID}
        type="stepAfter"
        dataKey={plotKey(entry.key)}
        stroke={entry.color}
        strokeWidth={2}
        dot={false}
        connectNulls
        isAnimationActive={false}
        name={entry.name}
      />
    )),
  ];
}
