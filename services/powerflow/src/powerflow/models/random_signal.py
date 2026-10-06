"""Time-bucketed random signals: a value that holds for a period (a second, a minute, an hour, or
any number of seconds), then jumps to a new random value around a nominal.

For quantities the simulator doesn't model physically (the grid frequency's small wander).
The draw depends only on (site seed, signal key, period bucket of the sim time), so a run is
reproducible, no clock is read, and different keys are independent streams.
"""

import math
import zlib
from dataclasses import dataclass
from datetime import datetime

import numpy as np

PERIOD_SECOND = 1.0
PERIOD_MINUTE = 60.0


@dataclass(frozen=True)
class RandomSignal:
    nominal: float
    spread: float  # the value is uniform in [nominal − spread, nominal + spread]
    period_s: float  # a new value every period (PERIOD_* or any number of seconds)
    key: str  # names the stream; signals with different keys are independent

    def __post_init__(self) -> None:
        if self.period_s <= 0 or self.spread < 0:
            raise ValueError("period_s must be > 0 and spread ≥ 0")

    def value_at(self, sim_time: datetime, seed: int) -> float:
        bucket = math.floor(sim_time.timestamp() / self.period_s)
        rng = np.random.default_rng((seed, zlib.crc32(self.key.encode()), bucket))
        return self.nominal + float(rng.uniform(-self.spread, self.spread))
