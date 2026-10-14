# Data sampling: lining up series and long windows

How backend-ot (and the historian in web-plusdas) handles the timestamps of readings: series from
different devices, series computed from other series, and windows too long to draw every reading.
Everything about it lives in this folder; the rest of the code calls in through a few hooks
(listed at the end).

## 1. Why this is needed

- **Devices are polled separately.** One poll cycle reads every device a few milliseconds apart
  (`.516`, `.520`, `.522`), so two points on different devices never share a timestamp exactly.
- **Windows can hold far more readings than a chart can draw.** At the default 10 s poll
  interval one point has:

  | Window | Readings per point |
  |---|---|
  | 1D | 8,640 |
  | 3D | 25,920 |
  | 1W | 60,480 |
  | 1M | 259,200 |
  | 3M | 777,600 |

  A trend holds up to 5 points, so a 3M trend would be ~3.9M readings.

## 2. Native (and standardized) points

Stored as polled: one row per reading in `device_points_readings`, at the poll's own timestamp.
They are never moved onto a grid. Everything below keeps those timestamps.

## 3. Lining up series across devices: `alignment.py`

When something needs values from several points at "the same time", it lines them up at their
own sample times, never at resampled ones:

- **One poll cycle is one aligned time.** Timestamps within `ALIGN_TOLERANCE` (1 s) of each
  other collapse into one aligned time, the cluster's last timestamp.
- **Each series carries its last value forward**, for at most `default_max_gap()`
  (`MAX_GAP_POLL_INTERVALS` = 3 poll intervals, 30 s by default), so one missed poll doesn't
  blank the result.
- **Missing data leaves a gap.** A time where a series has nothing that recent gives no value,
  never a made-up one.

Used by:
- **Virtual points** (`helpers/virtual_points/resolve.py::evaluate_series`): a calculation or
  condition over inputs on different devices gets one sample per poll cycle.
- **Site functions** that combine devices
  (`site_profiles/common/shared_helper_functions.py::spf_common_combine_series`), e.g. the site
  total of `site-energy-series`.

## 4. Site-function series follow their inputs' sample times

A site-profile endpoint declared with `output="series"` returns `series`: one `PointTimeseries`
or a list (enforced by `site_profiles/profile_registry.py`). Its samples keep the sample times of
the points it was computed from:
- derived one sample per input sample (e.g.
  `spf_common_cumulative_energy_kwh`: running kWh at each power sample's time);
- combined across devices with `spf_common_combine_series` (section 3).

So a function's line sits on the same timestamps as the raw points charted next to it.

## 5. The chart (web-plusdas, `src/features/historian/sampling/`)

- **Poll-cycle rows.** `buildChartRows` merges readings within `ROW_TOLERANCE_MS` (1000 ms, the
  same tolerance as `ALIGN_TOLERANCE`) into one row, at the cycle's last timestamp. Values are
  never changed. The discrete renderers (state lanes, step lines) use these rows.
- **One line per series.** Analog lines are drawn from each series' own samples
  (`buildLineSeries`), so a series keeps its own rate and lines stay continuous even when series
  don't share timestamps (as with plot values, below). A line breaks only at its own gap markers.
- **Tooltip.** For the hovered time it shows each series' latest sample at or before it.

## 6. Long windows: every reading up to 3 days, plot values beyond

A chart asks with `max_points` (about its width in pixels; the historian sends 2000). The
decision is made by **window length only**, in `policy.py::use_plot_values`, so it holds at any
poll rate:

| Window | What a chart gets |
|---|---|
| up to and including 3 days (`RAW_WINDOW_MAX`) | **Every reading at its actual timestamp.** `limit` is ignored, so nothing is capped (not even past the endpoint's 10,000). |
| longer than 3 days | **Plot values** (below). |

**Plot values** are a subset of the real readings, as OSIsoft PI plots long ranges. Nothing is
averaged, interpolated or invented:
- The window is cut into `max_points // 4` equal slices.
- Each slice keeps its **first, last, lowest and highest** reading, so every spike and dip still
  shows.
- An **enum, bitfield, status word or bool** point keeps each slice's first and last plus **every
  change of value**, so state lanes stay exact.

**Gap markers**, with `max_points`, for every window length: an outage (two readings more than
`default_max_gap()` apart) keeps both edge readings, and gets one marker sample with **no value**
at the gap's midpoint. A chart breaks the line there instead of bridging the outage. (The
readings endpoint leaves null fields out of its JSON, so a marker arrives as `{"time": ...}`.)

**Zoom refetches.** The historian sends the zoomed range as the window, so zooming in to 3 days
or less returns every reading again.

Where it runs:
- **Stored readings, over 3 days:** in Postgres (`plot_values_sql.py`). Only the kept rows and
  the markers reach Python.
- **Stored readings, up to 3 days:** read in full, markers added in Python
  (`plot_values.py::sample_readings`).
- **Virtual points:** computed in full from their inputs, then sampled in Python. Reducing the
  inputs first would be wrong: the minimum of a sum isn't the sum of the minimums.
- **Site functions:** the function computes on every reading (so totals like cumulative energy
  stay correct); only the returned `series` is sampled
  (`api/controllers/site_functions.py::run_site_endpoint` → `sample_series_response`).

## 7. Known limits

- **A raw 3-day window is heavy for the chart:** up to 26k readings per point at 10 s polling,
  130k for a 5-point trend, more at faster polling. The historian draws SVG (Recharts). If that is
  too slow, the next step is a canvas chart, not fewer readings.
- **Postgres still scans every reading in the window.** device_points_readings is a plain table
  (no TimescaleDB hypertable); a hypertable is the later fix for long windows.
- **Virtual points and site functions compute on all raw readings in Python** before sampling,
  so 1M/3M windows on them are slow.

Improvement steps (not done yet):
1. **Chart speed for raw 3-day windows:** measure the historian with a dense 3-day trend. If it
   is too slow, move its analog lines to a canvas chart (e.g. uPlot) rather than returning fewer
   readings. Tracked in web-plusdas `src/features/historian/sampling/README.md`.
2. **Database side of long windows:** make device_points_readings a TimescaleDB hypertable, so a
   1M/3M plot-values query doesn't scan every row.
3. **Virtual points and site functions over long windows:** they compute on every raw reading in
   Python before sampling. Find where this is slow (1M/3M) before optimizing.

## 8. Constants that must stay in step across services

| Constant | backend-ot | web-plusdas |
|---|---|---|
| One poll cycle | `alignment.py::ALIGN_TOLERANCE` = 1 s | `sampling/constants.ts::ROW_TOLERANCE_MS` = 1000 |
| Raw window | `policy.py::RAW_WINDOW_MAX` = 3 days | (decided by backend-ot only) |
| Plot values per series | `policy.py::MIN_PLOT_POINTS`..`MAX_PLOT_POINTS` = 100..5000 | `sampling/constants.ts::PLOT_POINTS` = 2000 |

## 9. Files and hooks

In this folder:

| File | What |
|---|---|
| `alignment.py` | Lining up series across devices (section 3). |
| `policy.py` | The 3-day rule and the `max_points` bounds and description. |
| `plot_values.py` | Plot values and gap markers in Python: `sample_series`, `sample_readings`, `sample_point_timeseries`, `sample_series_response`. |
| `plot_values_sql.py` | The same rule in Postgres: `plot_values_statement`. |

Hooks elsewhere (no sampling logic of their own):
- `helpers/reads/device_points_readings.py::get_timeseries_by_point_ids(max_points=...)`
- `api/routers/device_points_readings.py`: the `max_points` query parameter.
- `api/routers/site_functions.py`: series endpoints also accept `max_points`
  (`schemas/site_profiles/common.py::ChartParams`).
- `api/controllers/site_functions.py::run_site_endpoint`: samples the returned series.

Tests: `tests/unit/helpers/sampling/`, plus `TestChartSampling*` in
`tests/integration/api/routers/test_device_points_readings.py` and `TestSeriesChartSampling` in
`tests/integration/api/routers/test_site_functions.py`.
