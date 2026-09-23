"""Authoring tool: computes one day of plausible PV plant output.

**Not on the Modbus read path.** Registers never compute anything — they read
literals out of ``pv_profile_static``. This module exists to help you *write*
that table: call :func:`generate_pv_day`, look at the numbers, and paste the
ones you want in.

One public entry point, :func:`generate_pv_day`, returning a list of
:class:`PvSample`. It produces a *correlated* series — power, irradiance,
temperatures and wind all move together, because in a real plant they are all
driven by the same sun:

    2026-06-21T13:00  kw=2.62  ghi=997  poa=1147  ambient=23.9  module=61.3  wind=3.1

The AC power series is scaled from a nameplate in kW, so the same function
serves a 3 kW rooftop inverter and a 3.3 MW utility plant.

:func:`sun` is exposed separately because the shape alone is often what you
want when hand-building a table for one register.

Physics kept deliberately simple but not fake:

* **Irradiance** follows the half-sine day curve, peaking at ~1000 W/m² at solar
  noon and sitting at exactly zero overnight.
* **Plane-of-array** irradiance runs above horizontal (GHI), because the modules
  are tilted toward the sun.
* **Ambient temperature** lags the sun — it peaks mid-afternoon, not at noon,
  which is why it is a full-day sinusoid rather than the generation curve.
* **Module temperature** rises above ambient in proportion to irradiance (the
  NOCT rule of thumb), and is what actually costs you power.
* **AC power** is nameplate x sun x cloud, then derated by module temperature.
  This is why a real array almost never reaches its nameplate: at peak sun the
  modules are hot enough to give a few percent back.

Standard library only, and no imports from the rest of the app — this module
depends on nothing and nothing depends on it at runtime.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

MINUTES_PER_DAY = 1440
DEFAULT_INTERVAL_MINUTES = 5

# Daylight window. The half-sine peaks at the midpoint, putting solar noon at
# 13:00. This curve lives here, not in app/profiles.py, because it is an
# *authoring* tool: nothing on the Modbus read path computes a curve any more.
_PV_SUNRISE_HOUR = 6.0
_PV_SUNSET_HOUR = 20.0

# Clear-sky horizontal irradiance at solar noon, W/m².
_PEAK_GHI_W_M2 = 1000.0
# Tilted/tracked modules intercept more than a horizontal sensor does.
_POA_GAIN = 1.15

# Ambient air temperature: a full-day sinusoid peaking at _AMBIENT_PEAK_HOUR.
# Deliberately NOT the generation curve — air lags the sun by a few hours, so
# the hottest part of the day is mid-afternoon, well after peak output.
_AMBIENT_MEAN_C = 18.0
_AMBIENT_SWING_C = 9.0
_AMBIENT_PEAK_HOUR = 15.0

# NOCT rule of thumb: modules run ~30 °C above ambient at 800 W/m².
_NOCT_RISE_C = 30.0
_NOCT_IRRADIANCE_W_M2 = 800.0

# Power temperature coefficient: about -0.4 % per °C above the 25 °C rating point.
_TEMP_COEFF_PER_C = -0.004
_STC_TEMP_C = 25.0

# Wind: a light overnight breeze that freshens with the day's heating.
_WIND_BASE_M_S = 1.2
_WIND_DIURNAL_M_S = 2.5
_WIND_GUST_M_S = 0.6

# Cloud cover. Cubing a uniform draw keeps most samples near clear sky with the
# occasional deeper dip, which looks far more like real weather than uniform
# noise does.
_CLOUD_MAX_DIP = 0.55
# ...and cloud persists: each sample eases toward its target rather than being
# drawn independently, so a bank of cloud shades the array for a while instead
# of the series flickering between clear and overcast every 5 minutes. At 0.25
# the series has a time constant of roughly four samples (~20 min at 5-minute
# resolution).
_CLOUD_RESPONSE = 0.25


@dataclass(frozen=True)
class PvSample:
    """One interval of plant state."""

    timestamp: datetime
    kw: float
    irradiance_w_m2: float
    poa_irradiance_w_m2: float
    ambient_temp_c: float
    module_temp_c: float
    wind_speed_m_s: float


def sun(hour_of_day: float) -> float:
    """Clear-sky generation curve in ``[0, 1]``, peaking at solar noon.

    Exactly ``0.0`` outside the daylight window and continuous at both edges
    (``sin(0) == sin(pi) == 0``), so there is no step at sunrise or sunset.
    """
    day_length_hours = _PV_SUNSET_HOUR - _PV_SUNRISE_HOUR
    if hour_of_day <= _PV_SUNRISE_HOUR or hour_of_day >= _PV_SUNSET_HOUR:
        return 0.0
    return math.sin(math.pi * (hour_of_day - _PV_SUNRISE_HOUR) / day_length_hours)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ambient_temp_c(hour_of_day: float) -> float:
    """Air temperature, peaking at ``_AMBIENT_PEAK_HOUR``.

    Shifted so the sinusoid's maximum lands on the peak hour: ``sin`` peaks a
    quarter-turn in, hence the six-hour offset.
    """
    radians = 2.0 * math.pi * (hour_of_day - _AMBIENT_PEAK_HOUR + 6.0) / 24.0
    return _AMBIENT_MEAN_C + _AMBIENT_SWING_C * math.sin(radians)


def _module_temp_c(ambient_temp_c: float, irradiance_w_m2: float) -> float:
    """Module temperature — ambient plus a rise proportional to irradiance."""
    return ambient_temp_c + _NOCT_RISE_C * (irradiance_w_m2 / _NOCT_IRRADIANCE_W_M2)


def generate_pv_day(
    kw_max: float,
    day: Optional[date] = None,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    seed: Optional[int] = None,
) -> list[PvSample]:
    """A full day of PV output at ``interval_minutes`` resolution.

    At the 5-minute default this is 288 samples, midnight to 23:55 UTC.

    ``seed`` makes the weather reproducible; leave it ``None`` for a different
    day of clouds and gusts on every call. The sun curve is always
    deterministic — only cloud and wind gusts are random.
    """
    if kw_max <= 0:
        raise ValueError(f"kw_max must be positive, got {kw_max}")
    if interval_minutes <= 0 or MINUTES_PER_DAY % interval_minutes != 0:
        raise ValueError(
            f"interval_minutes must divide {MINUTES_PER_DAY} evenly, got {interval_minutes}"
        )

    day = day or datetime.now(timezone.utc).date()
    midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    rng = random.Random(seed)

    samples: list[PvSample] = []
    cloud = 1.0  # start clear; the smoothing below carries it forward
    for minute in range(0, MINUTES_PER_DAY, interval_minutes):
        hour_of_day = minute / 60.0
        sun_now = sun(hour_of_day)

        cloud_target = 1.0 - (rng.random() ** 3) * _CLOUD_MAX_DIP
        cloud += (cloud_target - cloud) * _CLOUD_RESPONSE
        irradiance = _PEAK_GHI_W_M2 * sun_now * cloud
        poa_irradiance = irradiance * _POA_GAIN

        ambient = _ambient_temp_c(hour_of_day)
        module = _module_temp_c(ambient, irradiance)

        temperature_derate = 1.0 + _TEMP_COEFF_PER_C * (module - _STC_TEMP_C)
        kw = _clamp(kw_max * sun_now * cloud * temperature_derate, 0.0, kw_max)

        wind = max(
            0.0,
            _WIND_BASE_M_S
            + _WIND_DIURNAL_M_S * sun_now
            + rng.uniform(-_WIND_GUST_M_S, _WIND_GUST_M_S),
        )

        samples.append(
            PvSample(
                timestamp=midnight + timedelta(minutes=minute),
                kw=round(kw, 3),
                irradiance_w_m2=round(irradiance, 1),
                poa_irradiance_w_m2=round(poa_irradiance, 1),
                ambient_temp_c=round(ambient, 1),
                module_temp_c=round(module, 1),
                wind_speed_m_s=round(wind, 2),
            )
        )
    return samples
