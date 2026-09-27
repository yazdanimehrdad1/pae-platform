"""Inverter math shared by the asset models."""

import math

from powerflow.site_config.models import Priority

# Relative slack when comparing against a rating, so float round-off never flags a limit.
RATING_TOLERANCE = 1e-9


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def limit_to_s_circle(
    p_kw: float, q_kvar: float, s_rated_kva: float, priority: Priority
) -> tuple[float, float, bool]:
    """Fit (P, Q) inside P² + Q² ≤ S². The priority quantity is kept (itself capped at S) and the
    other is reduced, keeping its sign. Returns (p, q, limited)."""
    if math.hypot(p_kw, q_kvar) <= s_rated_kva * (1 + RATING_TOLERANCE):
        return p_kw, q_kvar, False
    if priority is Priority.P:
        p_kw = clamp(p_kw, -s_rated_kva, s_rated_kva)
        q_kvar = math.copysign(math.sqrt(max(s_rated_kva**2 - p_kw**2, 0.0)), q_kvar)
    else:
        q_kvar = clamp(q_kvar, -s_rated_kva, s_rated_kva)
        p_kw = math.copysign(math.sqrt(max(s_rated_kva**2 - q_kvar**2, 0.0)), p_kw)
    return p_kw, q_kvar, True


def trim_q_to_s_circle(p_kw: float, q_kvar: float, s_rated_kva: float) -> tuple[float, bool]:
    """Reduce |Q| so (P, Q) fits the S circle, leaving P unchanged. Returns (q, limited)."""
    if math.hypot(p_kw, q_kvar) <= s_rated_kva * (1 + RATING_TOLERANCE):
        return q_kvar, False
    q_max = math.sqrt(max(s_rated_kva**2 - p_kw**2, 0.0))
    return math.copysign(q_max, q_kvar), True


def apparent_power(p_kw: float, q_kvar: float) -> float:
    return math.hypot(p_kw, q_kvar)


def power_factor(p_kw: float, q_kvar: float) -> float:
    """|P|/S, signed with the sign of Q (Q = 0 gives +). 1.0 when S = 0.

    For a generator (BESS/PV/POI export view) positive = injecting vars; for a load, positive =
    consuming vars (lagging)."""
    s_kva = math.hypot(p_kw, q_kvar)
    if s_kva == 0:
        return 1.0
    return math.copysign(abs(p_kw) / s_kva, q_kvar) if q_kvar != 0 else abs(p_kw) / s_kva


def q_from_power_factor(p_kw: float, pf: float) -> float:
    """Q for a signed power factor: positive pf = Q with the same sign convention as positive."""
    if pf == 0:
        raise ValueError("power factor can't be 0")
    return math.copysign(abs(p_kw) * math.tan(math.acos(min(abs(pf), 1.0))), pf)
