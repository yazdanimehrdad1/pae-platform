"""Register values, and the one small adapter that hands them to pymodbus.

Split deliberately in two:

:class:`RegisterValues`
    Everything that decides what a register reports. Plain class, no base class,
    no framework. Its entry point is :meth:`RegisterValues.read`, which is
    called from :meth:`MockRegisterBlock.getValues` below — so every method here
    has a visible caller inside this repo.

:class:`MockRegisterBlock`
    The adapter, and the *only* thing pymodbus touches. Three one-line methods,
    because pymodbus's datastore contract is exactly three methods:
    ``getValues``, ``setValues`` and ``validate``. They are the integration
    point, so they are the only code here without an in-repo caller — kept as
    thin as possible so nothing of substance hides behind the framework.
"""
from __future__ import annotations

import logging
import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pymodbus.datastore import ModbusSequentialDataBlock

from app.models import RegisterSpec, StaticProfile
from app.profiles import ProfileConfig, simulated_hour_of_day

logger = logging.getLogger("mock_modbus")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RegisterValues:
    """Produces the value for each register on demand.

    ``"random"`` draws uniformly within the register's bounds;
    ``"profile_static"`` looks the value up in ``static_profile`` by address,
    using the clock only to pick the row. Addresses absent from the metadata
    return ``default_value``.
    """

    def __init__(
        self,
        metadata: dict[int, RegisterSpec],
        default_value: int,
        rng: random.Random,
        label: str,
        profile_config: ProfileConfig | None = None,
        now_provider: Callable[[], datetime] = _utc_now,
        static_profile: StaticProfile | None = None,
    ) -> None:
        self.default_value = default_value
        self._metadata = metadata
        self._rng = rng
        self._label = label
        self._profile_config = profile_config or ProfileConfig()
        self._now_provider = now_provider
        self._static_profile = static_profile

        # Address -> (base address, word index). A 16-bit register maps to
        # itself at word 0; a 32-bit register claims two addresses, high word
        # first. Built once so the read path is a dict lookup.
        self._layout: dict[int, tuple[int, int]] = {}
        for address, spec in metadata.items():
            self._layout[address] = (address, 0)
            if spec.width == 32:
                low = address + 1
                if low in metadata:
                    raise ValueError(
                        f"{label}: {spec.name} is 32-bit so it occupies {address} and "
                        f"{low}, but {low} is declared separately as "
                        f"{metadata[low].name!r}"
                    )
                self._layout[low] = (address, 1)

        # Fail at startup, not on a client read halfway through the day.
        static_addresses = {
            address for address, spec in metadata.items() if spec.type == "profile_static"
        }
        if static_addresses:
            if static_profile is None:
                raise ValueError(
                    f"{label}: registers {sorted(static_addresses)} are "
                    'type="profile_static" but no static_profile was supplied'
                )
            # Intersection, not just the first row: an address is only usable if
            # EVERY slot supplies it, or a read would fall through a gap later.
            covered = set.intersection(*(set(row) for row in static_profile.rows.values()))
            missing = sorted(static_addresses - covered)
            if missing:
                raise ValueError(
                    f"{label}: static profile has no entry for addresses {missing} "
                    "in every row"
                )

    def read(self, address: int, count: int) -> list[int]:
        """Values for ``count`` registers starting at ``address``.

        Called by :meth:`MockRegisterBlock.getValues`.
        """
        result: list[int] = []
        # Read the clock once per request: a multi-register read must be a
        # single coherent snapshot, not one sampled across the day.
        now = self._now_provider()
        # One draw per 32-bit register per request, so its high and low words
        # belong to the same number rather than two unrelated ones.
        wide: dict[int, int] = {}
        for addr in range(address, address + count):
            base_word = self._layout.get(addr)
            if base_word is None:
                result.append(self.default_value)
                continue
            base, word = base_word
            entry = self._metadata[base]

            if entry.width == 32:
                if base not in wide:
                    wide[base] = self._rng.randint(entry.min, entry.max)
                value = (wide[base] >> 16) if word == 0 else wide[base]
            elif entry.type == "profile_static":
                value = self._static_value(now, base)
            else:
                value = self._rng.randint(entry.min, entry.max)
            # Modbus registers are unsigned 16-bit on the wire — wrap signed
            # (int16) values to their two's-complement uint16 representation.
            result.append(value & 0xFFFF)
        logger.info("READ %s address=%d count=%d -> %s", self._label, address, count, result)
        return result

    def _static_value(self, now: datetime, address: int) -> int:
        """Value for one address from the frozen table, snapped to its slot.

        ``PROFILE_DAY_MINUTES`` compresses the day, so a low value walks the
        table quickly. No interpolation: a read takes the slot it lands in.
        """
        assert self._static_profile is not None  # guaranteed by __init__
        hour_of_day = simulated_hour_of_day(now, self._profile_config)
        interval = self._static_profile.interval_minutes
        minute = int(hour_of_day * 60.0) // interval * interval
        slot = f"{minute // 60:02d}:{minute % 60:02d}"
        return self._static_profile.rows[slot][address]


class MockRegisterBlock(ModbusSequentialDataBlock):
    """Adapter between pymodbus's datastore contract and :class:`RegisterValues`.

    Deliberately contains no logic. pymodbus calls these three methods; each one
    either delegates to ``RegisterValues`` or is a deliberate no-op.
    """

    def __init__(self, values: RegisterValues) -> None:
        # One dummy slot keeps the base class happy; validate() below means
        # pymodbus never consults its range.
        super().__init__(1, [values.default_value])
        self._values = values

    def getValues(self, address: int, count: int = 1) -> list[int]:
        return self._values.read(address, count)

    def validate(self, _address: int, _count: int = 1) -> bool:
        # Always true: RegisterValues.read handles unmapped addresses itself.
        return True

    def setValues(self, _address: int, _values: Any) -> None:
        # Read-only mock: writes are accepted on the wire and discarded.
        pass


def build_device_blocks(
    holding_registers: dict[int, RegisterSpec],
    input_registers: dict[int, RegisterSpec],
    default_value: int = 0,
    seed: int | None = None,
    profile_config: ProfileConfig | None = None,
    now_provider: Callable[[], datetime] = _utc_now,
    static_profile: StaticProfile | None = None,
) -> tuple[MockRegisterBlock, MockRegisterBlock]:
    """Holding and input blocks for one device, sharing a single RNG."""
    rng = random.Random(seed)
    blocks = []
    for register_map, label in ((holding_registers, "holding"), (input_registers, "input")):
        values = RegisterValues(
            register_map,
            default_value,
            rng,
            label,
            profile_config=profile_config,
            now_provider=now_provider,
            static_profile=static_profile,
        )
        blocks.append(MockRegisterBlock(values))
    return blocks[0], blocks[1]
