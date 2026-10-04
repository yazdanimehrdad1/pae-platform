"""Energy counters the simulator doesn't keep: lifetime Wh/varh/VAh per device, by direction (and
by reactive quadrant for meters), plus today's Wh for PV.

`advance(snapshot)` integrates each device's latest P/Q over the sim time since the previous
snapshot (rectangle rule, P held over the step). The counters restart from 0 when the
simulation is reset (step_id goes back).
"""

import math
from dataclasses import dataclass
from datetime import date, datetime

from powerflow.core.snapshot import Snapshot

WH_PER_KWH = 1000.0
SECONDS_PER_HOUR = 3600.0


@dataclass
class Totals:
    """Accumulated energy for one device, in its own sign convention. Wh / varh / VAh."""

    wh_positive: float = 0.0
    wh_negative: float = 0.0
    varh_positive: float = 0.0
    varh_negative: float = 0.0
    vah_positive: float = 0.0  # while P ≥ 0
    vah_negative: float = 0.0  # while P < 0
    varh_quadrant: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    wh_positive_today: float = 0.0
    day: date | None = None

    def add(self, p_kw: float, q_kvar: float, hours: float, day: date) -> None:
        if day != self.day:
            self.day, self.wh_positive_today = day, 0.0
        p_wh, q_varh = p_kw * hours * WH_PER_KWH, q_kvar * hours * WH_PER_KWH
        s_vah = math.hypot(p_kw, q_kvar) * hours * WH_PER_KWH
        if p_wh >= 0:
            self.wh_positive += p_wh
            self.wh_positive_today += p_wh
            self.vah_positive += s_vah
        else:
            self.wh_negative -= p_wh
            self.vah_negative += s_vah
        if q_varh >= 0:
            self.varh_positive += q_varh
        else:
            self.varh_negative -= q_varh
        # Quadrants of the (P, Q) plane: Q1 P≥0 Q≥0, Q2 P<0 Q≥0, Q3 P<0 Q<0, Q4 P≥0 Q<0.
        quadrant = (0 if p_kw >= 0 else 1) if q_kvar >= 0 else (2 if p_kw < 0 else 3)
        values = list(self.varh_quadrant)
        values[quadrant] += abs(q_varh)
        self.varh_quadrant = (values[0], values[1], values[2], values[3])


def device_flows(snapshot: Snapshot) -> dict[str, tuple[float, float]]:
    """(P kW, Q kvar) of every metered thing, keyed like powerflow point prefixes."""
    flows: dict[str, tuple[float, float]] = {"poi.meter": (snapshot.poi.p_kw, snapshot.poi.q_kvar)}
    flows |= {f"bess.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.bess}
    flows |= {f"pv.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.pv}
    flows |= {f"load.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.loads}
    flows |= {f"meter.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.meters}
    return flows


class EnergyCounters:
    def __init__(self) -> None:
        self._totals: dict[str, Totals] = {}
        self._last: tuple[int, datetime] | None = None

    def reset(self) -> None:
        self._totals.clear()
        self._last = None

    def advance(self, snapshot: Snapshot) -> None:
        """Integrate up to this snapshot. The first snapshot (or one after a reset) only sets
        the starting point; repeating the same step does nothing."""
        if self._last is not None and snapshot.step_id < self._last[0]:
            self.reset()
        if self._last is None:
            self._last = (snapshot.step_id, snapshot.sim_time)
            return
        if snapshot.step_id == self._last[0]:
            return
        hours = (snapshot.sim_time - self._last[1]).total_seconds() / SECONDS_PER_HOUR
        day = snapshot.sim_time.date()
        for key, (p_kw, q_kvar) in device_flows(snapshot).items():
            self._totals.setdefault(key, Totals()).add(p_kw, q_kvar, hours, day)
        self._last = (snapshot.step_id, snapshot.sim_time)

    def totals(self, key: str) -> Totals:
        """The device's totals (all zero before its first integrated step)."""
        return self._totals.get(key, Totals())
