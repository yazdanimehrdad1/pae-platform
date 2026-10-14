// Sampling constants shared with backend-ot (see this folder's README.md).

// How many plot values a series may use: about a chart's width in pixels. Sent as `max_points`;
// backend-ot returns every reading for a window up to 3 days and plot values beyond (its bounds
// are 100..5000).
export const PLOT_POINTS = 2000;

// Devices are polled a moment apart, so one poll cycle's readings carry timestamps a few ms
// apart. Readings within this of a row's first one share that row. Same tolerance as backend-ot's
// ALIGN_TOLERANCE (helpers/sampling/alignment.py), which lines up virtual points and site functions.
export const ROW_TOLERANCE_MS = 1000;
