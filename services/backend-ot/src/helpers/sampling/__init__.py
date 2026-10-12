"""Time alignment and sampling of series for charts: README.md in this folder explains it all.

- alignment: lines up series from several devices at their own sample times (virtual points,
  site functions that combine devices).
- policy: up to RAW_WINDOW_MAX (3 days) every reading; beyond it, plot values.
- plot_values / plot_values_sql: the plot-value rule and gap markers, in Python and in Postgres.
"""

from helpers.sampling.alignment import (
    ALIGN_TOLERANCE,
    MAX_GAP_POLL_INTERVALS,
    align_series,
    aligned_times,
    default_max_gap,
)
from helpers.sampling.plot_values import (
    is_discrete,
    sample_point_timeseries,
    sample_readings,
    sample_series,
    sample_series_response,
)
from helpers.sampling.plot_values_sql import plot_values_statement
from helpers.sampling.policy import (
    MAX_PLOT_POINTS,
    MAX_POINTS_DESCRIPTION,
    MIN_PLOT_POINTS,
    RAW_WINDOW_MAX,
    use_plot_values,
)

__all__ = [
    "ALIGN_TOLERANCE",
    "MAX_GAP_POLL_INTERVALS",
    "MAX_PLOT_POINTS",
    "MAX_POINTS_DESCRIPTION",
    "MIN_PLOT_POINTS",
    "RAW_WINDOW_MAX",
    "align_series",
    "aligned_times",
    "default_max_gap",
    "is_discrete",
    "plot_values_statement",
    "sample_point_timeseries",
    "sample_readings",
    "sample_series",
    "sample_series_response",
    "use_plot_values",
]
