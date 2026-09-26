"""Calculations any site can reuse. Pure: no DB, no network, no clock."""

from datetime import datetime

from schemas.api_models import TimeseriesPoint

POWER_UNIT_TO_KW: dict[str, float] = {"W": 0.001, "kW": 1.0, "MW": 1000.0}


def power_to_kw_factor(unit: str | None) -> float:
    """Multiplier that converts a power point's unit to kW. Unknown units are an error."""
    if unit not in POWER_UNIT_TO_KW:
        raise ValueError(f"Unsupported power unit {unit!r}; expected one of {list(POWER_UNIT_TO_KW)}")
    return POWER_UNIT_TO_KW[unit]


def energy_kwh(samples: list[TimeseriesPoint], unit: str | None) -> float:
    """
    Energy in kWh from power samples, by trapezoidal integration over time.

    Samples may be in any order; null values are skipped. Fewer than two samples give 0.
    PLACEHOLDER: a gap in polling is bridged by a straight line, which over-counts
    energy across outages. A real site will need a max-gap rule.
    """
    factor = power_to_kw_factor(unit)
    readings: list[tuple[datetime, float]] = sorted(
        (s.time, s.value) for s in samples if s.value is not None
    )
    total = 0.0
    for (previous_time, previous_value), (current_time, current_value) in zip(
        readings, readings[1:], strict=False
    ):
        hours = (current_time - previous_time).total_seconds() / 3600
        total += (previous_value + current_value) / 2 * hours * factor
    return total


def average(samples: list[TimeseriesPoint]) -> float | None:
    """Mean of the non-null sample values; None when there are none."""
    values = [s.value for s in samples if s.value is not None]
    return sum(values) / len(values) if values else None
