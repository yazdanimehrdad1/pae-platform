"""Time-series profiles from CSV: linear interpolation, optional looping.

CSV format: a header row, a `timestamp` column (ISO 8601; naive timestamps are UTC) and one or
more numeric columns. Which value columns are required depends on the profile kind:
- load: `p_kw` and either `q_kvar` or `pf` (pf > 0 lagging/consuming vars, pf < 0 leading)
- pv (ac_kw source): `p_kw`
- pv (irradiance source): `ghi_wm2`
"""

import io
import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd

from powerflow.errors import ProfileError
from powerflow.models.common import q_from_power_factor
from powerflow.site_config.models import PvAvailabilitySource

FloatArray = npt.NDArray[np.float64]
TIMESTAMP_COLUMN = "timestamp"


class ProfileKind(StrEnum):
    LOAD = "load"
    PV_AC = "pv_ac_kw"
    PV_IRRADIANCE = "pv_irradiance"

    @classmethod
    def for_pv(cls, source: PvAvailabilitySource) -> "ProfileKind":
        if source is PvAvailabilitySource.IRRADIANCE:
            return cls.PV_IRRADIANCE
        return cls.PV_AC


@dataclass(frozen=True)
class Profile:
    """Sorted sample times (epoch s) and one array per value column."""

    times_s: FloatArray
    columns: dict[str, FloatArray]
    loop: bool
    scale: float = 1.0

    @property
    def start_s(self) -> float:
        return float(self.times_s[0])

    @property
    def end_s(self) -> float:
        return float(self.times_s[-1])

    @property
    def period_s(self) -> float:
        """Loop period: the span plus one (median) sample interval, so the last sample
        interpolates back into the first."""
        if len(self.times_s) < 2:
            return math.inf
        return self.end_s - self.start_s + float(np.median(np.diff(self.times_s)))

    def value_at(self, column: str, t_s: float) -> float:
        """Linear interpolation at epoch time t_s, times `scale`. Outside the profile: wraps
        around if `loop`, else holds the first/last value."""
        values = self.columns[column]
        if len(values) == 1:
            return float(values[0]) * self.scale
        times = self.times_s
        if self.loop:
            period = self.period_s
            t_s = self.start_s + (t_s - self.start_s) % period
            times = np.append(times, self.start_s + period)
            values = np.append(values, values[0])
        return float(np.interp(t_s, times, values)) * self.scale

    def values_at(self, t_s: float) -> dict[str, float]:
        return {column: self.value_at(column, t_s) for column in self.columns}


def _required_columns(kind: ProfileKind, header: list[str]) -> list[str]:
    if kind is ProfileKind.PV_AC:
        return ["p_kw"]
    if kind is ProfileKind.PV_IRRADIANCE:
        return ["ghi_wm2"]
    if "q_kvar" in header:
        return ["p_kw", "q_kvar"]
    if "pf" in header:
        return ["p_kw", "pf"]
    return ["p_kw", "q_kvar"]  # reported as missing below


def parse_profile_csv(text: str, kind: ProfileKind, loop: bool, scale: float = 1.0) -> Profile:
    try:
        frame = pd.read_csv(io.StringIO(text), skipinitialspace=True)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as error:
        raise ProfileError(f"can't parse CSV: {error}") from error
    frame.columns = [str(column).strip() for column in frame.columns]
    header = list(frame.columns)
    required = [TIMESTAMP_COLUMN, *_required_columns(kind, header)]
    missing = [column for column in required if column not in header]
    if missing:
        raise ProfileError(f"{kind} profile is missing column(s) {missing}; has {header}")
    if frame.empty:
        raise ProfileError("profile has no rows")

    try:
        timestamps = pd.to_datetime(frame[TIMESTAMP_COLUMN], utc=True, format="ISO8601")
    except (ValueError, TypeError) as error:
        raise ProfileError(f"bad timestamp: {error}") from error
    times_s = timestamps.map(lambda stamp: stamp.timestamp()).to_numpy(dtype=np.float64)

    columns: dict[str, FloatArray] = {}
    for column in required[1:]:
        values = np.asarray(pd.to_numeric(frame[column], errors="coerce"), dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise ProfileError(f"column {column!r} has non-numeric or empty values")
        columns[column] = values

    order = np.argsort(times_s, kind="stable")
    times_s = times_s[order]
    if np.any(np.diff(times_s) == 0):
        raise ProfileError("duplicate timestamps")
    columns = {column: values[order] for column, values in columns.items()}

    if "pf" in columns:
        pf = columns.pop("pf")
        if np.any(pf == 0) or np.any(np.abs(pf) > 1):
            raise ProfileError("pf must be in [-1, 0) or (0, 1]")
        columns["q_kvar"] = np.array(
            [q_from_power_factor(p, f) for p, f in zip(columns["p_kw"], pf, strict=True)],
            dtype=np.float64,
        )
    return Profile(times_s=times_s, columns=columns, loop=loop, scale=scale)


def load_profile_file(path: Path, kind: ProfileKind, loop: bool, scale: float) -> Profile:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProfileError(f"can't read profile {path}: {error}") from error
    try:
        return parse_profile_csv(text, kind, loop, scale)
    except ProfileError as error:
        raise ProfileError(f"{path}: {error}") from error
