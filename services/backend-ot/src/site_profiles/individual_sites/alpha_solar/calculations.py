"""Calculations only Alpha Solar Farm needs. Pure: no DB, no network, no clock."""

from schemas.api_models import TimeseriesPoint


def count_online_samples(states: list[TimeseriesPoint], online_states: frozenset[int]) -> int:
    """SAMPLE: how many state samples hold a code that counts as available."""
    return sum(1 for s in states if s.value is not None and int(s.value) in online_states)


def availability_pct(online_samples: int, total_samples: int) -> float | None:
    """Share of samples that were online, in percent; None when there are no samples."""
    return online_samples / total_samples * 100 if total_samples else None
