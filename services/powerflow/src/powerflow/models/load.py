"""Site load model: profile value × scale, plus optional seeded Gaussian noise. Pure Python.

Load convention: P > 0 consumes, Q > 0 consumes vars (lagging).
"""

from dataclasses import dataclass

import numpy as np

from powerflow.models.common import apparent_power, power_factor
from powerflow.site_config.models import NoiseConfig


@dataclass(frozen=True)
class LoadOutput:
    p_kw: float
    q_kvar: float

    @property
    def s_kva(self) -> float:
        return apparent_power(self.p_kw, self.q_kvar)

    @property
    def pf(self) -> float:
        return power_factor(self.p_kw, self.q_kvar)


def load_output(
    p_kw: float, q_kvar: float, noise: NoiseConfig | None, rng: np.random.Generator
) -> LoadOutput:
    """The load for one step. Noise is a relative Gaussian (std in % of the value)."""
    if noise is not None:
        p_kw *= 1.0 + rng.normal(0.0, noise.p_std_pct / 100.0)
        q_kvar *= 1.0 + rng.normal(0.0, noise.q_std_pct / 100.0)
    return LoadOutput(float(p_kw), float(q_kvar))
