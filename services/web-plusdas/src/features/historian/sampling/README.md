# Historian sampling (web-plusdas side)

How the historian charts readings without moving them onto a grid. The full story, including how
backend-ot lines up virtual points and site functions and samples long windows, is in
backend-ot's `src/helpers/sampling/README.md`. This folder is the chart's half.

## What the chart asks for

Every readings and site-function request is a chart request: `max_points = PLOT_POINTS` (2000)
with the window the chart shows (`hooks/useHistorianSeries.ts`). backend-ot then returns:

| Window | Returned |
|---|---|
| up to and including 3 days | every reading at its actual timestamp (no 10,000 cap) |
| longer than 3 days | plot values: real readings only, each slice's first, last, lowest and highest (enum/bit points: every change) |

Either way an outage (no reading for more than 3 poll intervals) comes with a **gap marker**: a
sample with no value at the gap's midpoint.

**Zoom refetches.** `TrendChart` sends the zoomed range as the window, so zooming in to 3 days
or less brings back every reading. The previous data stays on screen while it loads.

## How it is drawn

| Piece | File | What |
|---|---|---|
| Rows | `chartRows.ts::buildChartRows` | One row per poll cycle: readings within `ROW_TOLERANCE_MS` (1 s) share a row, at the cycle's last timestamp. Gap markers left out. Used by the discrete renderers (state lanes, step lines) and for hover positions. |
| Lines | `chartRows.ts::buildLineSeries` | Each analog line gets its own samples, `{ timestamp, [selectionId]: value }`, every sample it received, gap markers kept as `null`. Series that don't share timestamps (plot values, different devices) still draw continuous lines, and a line breaks only at its own outages. |
| Tooltip | `tooltip.ts::latestAtOrBefore` | For the hovered time, each line's latest sample at or before it. Nothing before its first sample or inside an outage. |
| Constants | `constants.ts` | `PLOT_POINTS`, `ROW_TOLERANCE_MS`. |

Analog lines are `type="linear"` with animation off: a 3-day line can hold ~26k points.

## Kept in step with backend-ot

- `ROW_TOLERANCE_MS` (1000) = backend-ot `ALIGN_TOLERANCE` (1 s).
- `PLOT_POINTS` (2000) must stay within backend-ot's `max_points` bounds (100..5000, in the
  contract).
- The 3-day rule is backend-ot's alone (`RAW_WINDOW_MAX`); the chart doesn't need to know it.

## Improvements (not done yet)

1. **Measure and, if needed, speed up drawing a raw 3-day window.** A dense 3-day line is ~26k
   points at 10 s polling (130k for a 5-point trend). Recharts draws SVG, so this may be slow;
   it hasn't been measured in a browser yet. If it is too slow, switch the analog lines to a
   canvas chart (e.g. uPlot) rather than sending fewer readings. That adds a dependency, so agree
   it first.
2. **Give the alarms page trend the same chart request.** `features/alarms/hooks/useAlarmsData.ts`
   calls the readings endpoint without `max_points`, so it gets the 1000 most recent readings of
   its window. Move `PLOT_POINTS` somewhere both features can use (e.g. `src/shared/`) and send it.

Tests: `tests/features/historian/sampling/`.
