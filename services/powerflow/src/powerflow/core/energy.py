"""Energy counters: P and Q of every device integrated over each converged step.

Pure functions, called from `simulate_step`: every step adds P·dt (dt = the step's real length,
so skipped ticks and `sim/step?count=N` are integrated exactly), nothing is integrated while the
power flow doesn't converge, and the totals restart with the simulation (reset, activate). The
totals ride on the snapshot (each measurement's `energy`, plus a few kWh measurement points).
"""

import math
from datetime import date

from powerflow.core.snapshot import EnergyTotals, Snapshot

SECONDS_PER_HOUR = 3600.0
WH_PER_KWH = 1000.0


def accumulate(
    totals: EnergyTotals, p_kw: float, q_kvar: float, hours: float, day: date
) -> EnergyTotals:
    """Totals after P/Q held for `hours`, in the device's own sign convention."""
    p_wh = p_kw * hours * WH_PER_KWH
    q_varh = q_kvar * hours * WH_PER_KWH
    s_vah = math.hypot(p_kw, q_kvar) * hours * WH_PER_KWH
    today = totals.wh_positive_today if totals.day == day else 0.0
    quadrant = {
        (True, True): "varh_q1",
        (False, True): "varh_q2",
        (False, False): "varh_q3",
        (True, False): "varh_q4",
    }[(p_wh >= 0, q_varh >= 0)]
    update: dict[str, float | date] = {
        "wh_positive": totals.wh_positive + max(p_wh, 0.0),
        "wh_negative": totals.wh_negative + max(-p_wh, 0.0),
        "varh_positive": totals.varh_positive + max(q_varh, 0.0),
        "varh_negative": totals.varh_negative + max(-q_varh, 0.0),
        "vah_positive": totals.vah_positive + (s_vah if p_wh >= 0 else 0.0),
        "vah_negative": totals.vah_negative + (s_vah if p_wh < 0 else 0.0),
        quadrant: getattr(totals, quadrant) + abs(q_varh),
        "wh_positive_today": today + max(p_wh, 0.0),
        "day": day,
    }
    return totals.model_copy(update=update)


def device_flows(snapshot: Snapshot) -> dict[str, tuple[float, float]]:
    """(P kW, Q kvar) of every metered thing, keyed like the powerflow point prefixes."""
    flows: dict[str, tuple[float, float]] = {"poi.meter": (snapshot.poi.p_kw, snapshot.poi.q_kvar)}
    flows |= {f"bess.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.bess}
    flows |= {f"pv.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.pv}
    flows |= {f"load.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.loads}
    flows |= {f"meter.{item.id}": (item.p_kw, item.q_kvar) for item in snapshot.meters}
    return flows


def integrate(
    previous: dict[str, EnergyTotals], snapshot: Snapshot, dt_s: float
) -> dict[str, EnergyTotals]:
    """Every device's totals after this (converged) step of length dt_s."""
    hours = dt_s / SECONDS_PER_HOUR
    day = snapshot.sim_time.date()
    return {
        key: accumulate(previous.get(key, EnergyTotals()), p_kw, q_kvar, hours, day)
        for key, (p_kw, q_kvar) in device_flows(snapshot).items()
    }


def attach(snapshot: Snapshot, energy: dict[str, EnergyTotals]) -> Snapshot:
    """The snapshot with each measurement's totals and kWh points filled in."""

    def totals(key: str) -> EnergyTotals:
        return energy.get(key, EnergyTotals())

    def kwh(value: float) -> float:
        return value / WH_PER_KWH

    poi = totals("poi.meter")
    return snapshot.model_copy(
        update={
            "poi": snapshot.poi.model_copy(
                update={
                    "energy": poi,
                    "energy_export_kwh": kwh(poi.wh_positive),
                    "energy_import_kwh": kwh(poi.wh_negative),
                }
            ),
            "bess": [
                item.model_copy(
                    update={
                        "energy": (bess := totals(f"bess.{item.id}")),
                        "energy_discharged_kwh": kwh(bess.wh_positive),
                        "energy_charged_kwh": kwh(bess.wh_negative),
                    }
                )
                for item in snapshot.bess
            ],
            "pv": [
                item.model_copy(
                    update={
                        "energy": (pv := totals(f"pv.{item.id}")),
                        "energy_produced_kwh": kwh(pv.wh_positive),
                        "energy_produced_today_kwh": kwh(pv.wh_positive_today),
                    }
                )
                for item in snapshot.pv
            ],
            "loads": [
                item.model_copy(
                    update={
                        "energy": (load := totals(f"load.{item.id}")),
                        "energy_consumed_kwh": kwh(load.wh_positive),
                    }
                )
                for item in snapshot.loads
            ],
            "meters": [
                item.model_copy(
                    update={
                        "energy": (meter := totals(f"meter.{item.id}")),
                        "energy_export_kwh": kwh(meter.wh_positive),
                        "energy_import_kwh": kwh(meter.wh_negative),
                    }
                )
                for item in snapshot.meters
            ],
        }
    )
