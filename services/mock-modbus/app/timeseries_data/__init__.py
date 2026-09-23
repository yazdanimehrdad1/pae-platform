"""Timeseries generators for mock plant output.

Where ``app/modbus_mock_data`` describes *registers* (an address and the band its
value lives in), this package describes *a day of plant behaviour* — a whole
correlated series of power, irradiance, temperature and wind at a fixed
interval, scaled from a device's ``kw_max`` nameplate.

Two modules, one that authors and one that serves:

``pv_day_generator``
    The authoring tool. One function, :func:`generate_pv_day`, which owns the sun
    curve and COMPUTES a day from a nameplate, an interval and a weather seed,
    returning :class:`PvSample` rows. Use it to write or retune the table below.
    **Nothing on the Modbus read path calls it**, and it imports nothing from the
    rest of the app.

``pv_profile_static``
    A FROZEN table of literal register values, 288 rows at five-minute
    resolution, keyed by ``"HH:MM"`` then by **register address**. This one *is*
    on the read path: registers declared ``type="profile_static"`` look
    themselves up in it by address.

Each address in the static table is an independent column, so it can express
what a single shared curve could not — ambient temperature peaking
mid-afternoon, power derated by module temperature.

Import from the modules directly; this package deliberately re-exports nothing::

    from app.timeseries_data.pv_day_generator import generate_pv_day
    from app.timeseries_data.pv_profile_static import PV_PROFILE_STATIC
"""
from __future__ import annotations
