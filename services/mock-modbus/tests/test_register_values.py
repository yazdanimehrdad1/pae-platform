"""The datastore read path in isolation, with a pinned clock.

Invariant guarded: how one read turns a register spec into wire values — random draws
stay in band and are reproducible under a seed, static registers read exactly the row
their slot selects, 32-bit registers are one coherent number, signed values wrap to
two's complement, and misconfiguration fails at build time rather than on a read.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from app.datastore import RegisterValues
from app.models import RegisterSpec, StaticProfile

PINNED_NOW = datetime(2026, 1, 1, 13, 2, 30, tzinfo=UTC)  # lands in the "13:00" slot
DEFAULT_VALUE = 7


def _values(
    metadata: dict[int, RegisterSpec],
    *,
    seed: int = 1,
    static_profile: StaticProfile | None = None,
) -> RegisterValues:
    return RegisterValues(
        metadata,
        DEFAULT_VALUE,
        random.Random(seed),
        "holding",
        now_provider=lambda: PINNED_NOW,
        static_profile=static_profile,
    )


class TestRandomRegisters:
    def test_draws_stay_inside_the_band(self) -> None:
        values = _values({1: RegisterSpec(name="voltage", type="random", min=470, max=490)})
        assert all(470 <= values.read(1, 1)[0] <= 490 for _ in range(200))

    def test_same_seed_gives_the_same_sequence(self) -> None:
        spec = {1: RegisterSpec(name="voltage", type="random", min=0, max=65535)}
        first, second = _values(spec, seed=42), _values(spec, seed=42)
        assert [first.read(1, 1) for _ in range(20)] == [second.read(1, 1) for _ in range(20)]

    def test_negative_values_wrap_to_twos_complement(self) -> None:
        values = _values({1: RegisterSpec(name="current", type="random", min=-5, max=-5)})
        assert values.read(1, 1) == [0xFFFB]


class TestThirtyTwoBitRegisters:
    def test_both_words_come_from_one_draw(self) -> None:
        spec = RegisterSpec(name="energy", type="random", width=32, min=70_000, max=70_000)
        values = _values({10: spec})
        high, low = values.read(10, 2)
        assert (high << 16) | low == 70_000

    def test_declaring_the_low_word_separately_fails_at_build(self) -> None:
        with pytest.raises(ValueError, match="32-bit"):
            _values(
                {
                    10: RegisterSpec(name="energy", type="random", width=32, min=0, max=1),
                    11: RegisterSpec(name="other", type="random", min=0, max=1),
                }
            )


class TestStaticRegisters:
    TABLE = StaticProfile(
        interval_minutes=60,
        rows={f"{hour:02d}:00": {4: hour * 10} for hour in range(24)},
    )

    def test_reads_the_row_for_the_current_slot(self) -> None:
        values = _values(
            {4: RegisterSpec(name="active_power", type="profile_static", min=0, max=1000)},
            static_profile=self.TABLE,
        )
        assert values.read(4, 1) == [130]  # 13:02 snaps down to the 13:00 row

    def test_address_missing_from_the_table_fails_at_build(self) -> None:
        with pytest.raises(ValueError, match="no entry for addresses"):
            _values(
                {5: RegisterSpec(name="irradiance", type="profile_static", min=0, max=1000)},
                static_profile=self.TABLE,
            )


class TestUnmapped:
    def test_unmapped_addresses_serve_the_default(self) -> None:
        values = _values({1: RegisterSpec(name="voltage", type="random", min=5, max=5)})
        assert values.read(1, 3) == [5, DEFAULT_VALUE, DEFAULT_VALUE]
