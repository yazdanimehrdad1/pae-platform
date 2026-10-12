"""When a chart gets every reading and when it gets plot values (see README.md, "Long windows").

Decided by the window's length, never by how many readings it holds, so a window of up to
RAW_WINDOW_MAX always returns every reading at its actual timestamp, at any poll rate.
"""

from datetime import datetime, timedelta

RAW_WINDOW_MAX = timedelta(days=3)

# Bounds of the `max_points` query parameter (how many plot values a chart can use).
MIN_PLOT_POINTS = 100
MAX_PLOT_POINTS = 5000

MAX_POINTS_DESCRIPTION = (
    "For a chart: how many plot values a series may use (about the chart's width in pixels). Needs a "
    "time window (and overrides `limit` where the route has one). A window up to 3 days returns every reading at its "
    "actual timestamp; a longer one returns plot values: real readings only, each slice's first, "
    "last, lowest and highest (enum and bit points: every change). Either way an outage longer than "
    "3 poll intervals gets a gap marker, a sample with no value at the gap's midpoint."
)


def use_plot_values(start: datetime | None, end: datetime | None, max_points: int | None) -> bool:
    """True only when a chart asked for plot values (max_points) over a window longer than
    RAW_WINDOW_MAX. A window of exactly RAW_WINDOW_MAX is still raw."""
    return max_points is not None and start is not None and end is not None and end - start > RAW_WINDOW_MAX
