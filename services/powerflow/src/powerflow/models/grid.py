"""Grid frequency. The power flow is steady-state at nominal frequency; the reported frequency is
the nominal (or an injected excursion) plus a small time-bucketed wander, the same for every
device on the site. A de-energised site reports 0 Hz.
"""

from datetime import datetime

from powerflow.models.random_signal import PERIOD_SECOND, RandomSignal

NOMINAL_HZ = 60.0
# The wander around the nominal (or the injected value): ±0.02 Hz, a new value every second.
GRID_HZ_WANDER = RandomSignal(nominal=0.0, spread=0.02, period_s=PERIOD_SECOND, key="grid_hz")


def grid_frequency_hz(
    sim_time: datetime, seed: int, override_hz: float | None, energized: bool
) -> float:
    if not energized:
        return 0.0
    center = override_hz if override_hz is not None else NOMINAL_HZ
    return center + GRID_HZ_WANDER.value_at(sim_time, seed)
