"""Regenerate the profile scenarios in profiles/ (24 h, 1-minute, deterministic).

Usage: uv run python scripts/make_profiles.py

Load scenarios (timestamp,p_kw,q_kvar at pf 0.95):
  typical          commercial day, ~2.2 MW evening peak
  high_demand      the same shape, 3 MW peak
  low_demand       ~1.2 MW peak
  evening_peak     low base with a sharp 3 MW evening spike (peak-shaving tests)
  flat_industrial  ~2 MW around the clock, with a day/night shift step

PV scenarios (timestamp,p_kw,ghi_wm2; p_kw is available AC for a 5 MWac / 6.5 MWp plant
before inverter clipping):
  clear_sky_high   clear day, peaking at the inverter limit
  overcast_low     overcast day, ~25 % of clear sky
  cloudy_dynamic   passing clouds with minute-scale ramps (seeded)
  clipping_heavy   very sunny day, well above the 5 MWac limit
"""

import math
import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"
DAY_START = datetime(2026, 6, 21, tzinfo=UTC)
MINUTES_PER_DAY = 24 * 60
LOAD_POWER_FACTOR = 0.95
SUNRISE_HOUR, SUNSET_HOUR = 5.5, 20.5
CLOUD_SEED = 7


def gaussian(hour: float, center: float, width: float) -> float:
    return math.exp(-(((hour - center) / width) ** 2))


def commercial_load(peak_kw: float) -> Callable[[float], float]:
    """Night base at 40 % of peak, a morning bump and an evening peak at 18:00."""

    def shape(hour: float) -> float:
        base = 0.4 * peak_kw
        morning = 0.35 * peak_kw * gaussian(hour, 9.0, 2.5)
        evening = 0.6 * peak_kw * gaussian(hour, 18.0, 2.2)
        return min(base + morning + evening, peak_kw)

    return shape


def evening_peak_load(hour: float) -> float:
    return 800.0 + 2200.0 * gaussian(hour, 19.0, 0.9)


def flat_industrial_load(hour: float) -> float:
    return 2200.0 if 6.0 <= hour < 22.0 else 1800.0


def clear_sky(hour: float) -> float:
    """0..1 clear-sky bell between sunrise and sunset."""
    if not SUNRISE_HOUR < hour < SUNSET_HOUR:
        return 0.0
    angle = math.pi * (hour - SUNRISE_HOUR) / (SUNSET_HOUR - SUNRISE_HOUR)
    return math.sin(angle) ** 1.5


def overcast(hour: float) -> float:
    """A diffuse, flatter curve at about a quarter of clear sky."""
    return 0.25 * clear_sky(hour) ** 0.7


def cloud_factors() -> list[float]:
    """Per-minute transmission for a day of passing clouds: clear spells and cloud shadows
    (20-45 % transmission) lasting 3-25 min, with one-minute edges."""
    rng = random.Random(CLOUD_SEED)
    factors: list[float] = []
    cloudy = False
    while len(factors) < MINUTES_PER_DAY:
        duration = rng.randint(3, 25)
        level = rng.uniform(0.2, 0.45) if cloudy else rng.uniform(0.9, 1.0)
        factors.extend([level] * duration)
        cloudy = not cloudy
    return factors[:MINUTES_PER_DAY]


def write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as csv_file:
        csv_file.write(header + "\n")
        csv_file.write("\n".join(rows) + "\n")
    print(f"wrote {path}")


def stamp(minute: int) -> str:
    return (DAY_START + timedelta(minutes=minute)).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_load(name: str, shape: Callable[[float], float]) -> None:
    tan_phi = math.tan(math.acos(LOAD_POWER_FACTOR))
    rows = []
    for minute in range(MINUTES_PER_DAY):
        p_kw = shape(minute / 60.0)
        rows.append(f"{stamp(minute)},{p_kw:.1f},{p_kw * tan_phi:.1f}")
    write_csv(PROFILES_DIR / "load" / f"{name}.csv", "timestamp,p_kw,q_kvar", rows)


def write_pv(name: str, shape: Callable[[int], float], peak_ac_kw: float, peak_ghi: float) -> None:
    rows = []
    for minute in range(MINUTES_PER_DAY):
        fraction = shape(minute)
        rows.append(f"{stamp(minute)},{peak_ac_kw * fraction:.1f},{peak_ghi * fraction:.1f}")
    write_csv(PROFILES_DIR / "pv" / f"{name}.csv", "timestamp,p_kw,ghi_wm2", rows)


def main() -> None:
    write_load("typical", commercial_load(2200.0))
    write_load("high_demand", commercial_load(3000.0))
    write_load("low_demand", commercial_load(1200.0))
    write_load("evening_peak", evening_peak_load)
    write_load("flat_industrial", flat_industrial_load)

    clouds = cloud_factors()
    write_pv("clear_sky_high", lambda minute: clear_sky(minute / 60.0), 5000.0, 1000.0)
    write_pv("overcast_low", lambda minute: overcast(minute / 60.0), 5000.0, 1000.0)
    write_pv(
        "cloudy_dynamic",
        lambda minute: clear_sky(minute / 60.0) * clouds[minute],
        5200.0,
        1000.0,
    )
    write_pv("clipping_heavy", lambda minute: clear_sky(minute / 60.0), 6500.0, 1050.0)


if __name__ == "__main__":
    main()
