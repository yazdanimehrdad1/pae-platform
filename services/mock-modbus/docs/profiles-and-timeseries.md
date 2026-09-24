# Profile registers and timeseries data

> How `type="profile_static"` registers get their values, the frozen table, the offline
> generator, and which registers are safe to profile.

## Timeseries data

[app/timeseries_data/](../app/timeseries_data/) generates a **whole day of correlated plant
behaviour** — power, irradiance, temperatures and wind that all move together because
they share one sun. This is a different thing from a register map: a register map says
"address 4 lives in [1000, 2900]"; a timeseries says "here is what the whole plant
did today, minute by minute".

**It is not wired into the Modbus read path.** Nothing in `getValues` consults it. It
exists to be used by callers, and as the obvious foundation if registers are ever made
to replay a series.

### `pv_day_generator.py` — the authoring tool

**Not on the read path.** It owns the sun curve and produces a day of correlated PV
output; its job is to help you *write* the static table (and to inspect a plausible
day). Nothing at runtime calls it.

[app/timeseries_data/pv_day_generator.py](../app/timeseries_data/pv_day_generator.py) — one day of PV
output at a fixed interval (**5 minutes by default = 288 samples**, midnight to 23:55
UTC). AC power is scaled from the device's `kw_max`, so one generator serves a 3 kW
rooftop inverter and a 3.3 MW plant.

**One public entry point**, plus the curve on its own:

```python
from app.timeseries_data.pv_day_generator import generate_pv_day, sun

samples = generate_pv_day(kw_max=3300.0, seed=42)   # 288 PvSample
samples[156].kw, samples[156].irradiance_w_m2       # 2585.6, 906.1

sun(13.0)   # 1.0  — the bare shape, for hand-building one register's column
```

Each `PvSample` carries `timestamp, kw, irradiance_w_m2, poa_irradiance_w_m2,
ambient_temp_c, module_temp_c, wind_speed_m_s`.

There is **no CLI** — the module is a library you import from a generator script,
not something run on its own. It also imports nothing from the rest of the app, so
it can be lifted out or rewritten without touching the server.

The physics is simple but not fake, and the details are the point:

- **The sun curve lives here**, in `sun(hour_of_day)`. It is deliberately *not* in
  `app/profiles.py` any more: no curve is evaluated at read time, so the curve is an
  authoring concern only.
- **Ambient temperature peaks mid-afternoon (15:00), not at solar noon** — air lags the
  sun. That is why it is a full-day sinusoid rather than the generation curve.
- **Module temperature drives a power derate** (−0.4 %/°C above 25 °C), which is why
  peak output lands around 78–85 % of nameplate rather than 100 %. A mock that hit its
  nameplate at noon would be the giveaway that it is a mock.
- **Cloud persists.** Each sample eases toward its target (~20 min time constant)
  instead of being drawn independently, so the series shades and clears like weather
  rather than flickering every 5 minutes.
- `generate_pv_day` **raises** on a non-positive `kw_max` or an interval that does not
  divide the day evenly, rather than producing a quietly wrong series.

### `pv_profile_static.py` — frozen

A literal dictionary, **288 rows at five-minute resolution**, keyed by `"HH:MM"` and
then by **register address**:

```python
PV_PROFILE_STATIC = StaticProfile(
    interval_minutes=5,
    rows={
        "00:00": {4: 1000, 1007: 100, 1008: 151, 1009: 223},
        ...
        "13:00": {4: 2604, 1007: 1100, 1008: 427, 1009: 639},
        "15:00": {4: 2458, 1007: 1001, 1008: 450, 1009: 621},
    },
)
```

Unlike the generator above, **this one is on the Modbus read path** — `device_1`'s
`profile_static` registers read straight out of it. Edit a number and that is exactly
what the register reports at that time; nothing is recomputed behind your back, and a
diff shows precisely what changed.

Keyed by **address** rather than name so a row survives a register rename and reads
like the register map a client actually talks to.

**The table is a pydantic model**, `StaticProfile` in [app/models.py](../app/models.py) —
deliberately just types: `interval_minutes: int` and `rows: dict[str, dict[int, int]]`,
nothing else. Pydantic checks the shape for free, so a non-integer address or value is
rejected at import. No custom validators, no methods.

The behaviour lives in [app/datastore.py](../app/datastore.py) instead:

- **Lookup** — `MockRegisterBlock._static_value` snaps the hour down to its slot,
  formats the `"HH:MM"` key and indexes `rows`. No interpolation.
- **Coverage** — at block-build time it intersects the address sets of *every* row and
  rejects any `profile_static` register not present in all of them, so a mis-declared
  register fails before the server accepts a connection.

Not checked anywhere: a deleted row or a mistyped key (`"13:0"`). Those surface as a
`KeyError` when a read lands on that slot — a loud failure rather than a wrong value.

The initial values were generated from the shared sun curve, but the file is now plain
data. It already encodes two things the single curve cannot: ambient temperature
peaking at 15:00 (air lags the sun) and active power derated by module temperature, so
4 tops out near 2604 rather than touching its 2900 ceiling.

## Profiling a register

A register is either `"random"` or `"profile_static"` — there is no third mode, and
nothing computes a curve at read time. Opting in is a per-register decision:

1. Set `type="profile_static"` on the `RegisterSpec`.
2. Add that register's **address** to every row of its device's frozen table.

Miss step 2 and the server **fails at startup**, not on a client read halfway through
the day.

**Current state:** `device_1` is the worked example — 54 registers: **13
`profile_static`** (holding 2, 4–8, 10; input 1004–1009) and **41 `random`**.
`device_2` and `device_3` are entirely random, and would each need their own table
(the existing one is keyed by device_1's addresses) before anything in them could be
made static.

`pv_profile_static.py` still carries a column for address **1**, which nothing
reads — `dc_bus_voltage` is currently `type="random", min=0, max=4`. Harmless (the
coverage check only requires declared registers to be present, not the reverse), but
it means the table and the register map have drifted apart by one address.

`device_type` (`pv` / `bess` / `ied`) no longer selects a curve — there are no curves.
It now only selects *which frozen table* a device's static registers read from; see
`_static_profile_for` in [app/server.py](../app/server.py). Today only `pv` has one.

**Every register in every device file states `type=` explicitly** — all 155, including
the 142 that are `"random"`, which is already the default. That is deliberate: an
absent `type` reads as "nobody thought about this one" rather than "random on
purpose". Keep it that way when adding a register.

To see it without waiting for noon, compress the day:

```bash
PROFILE_DAY_MINUTES=2 ZERO_MODE=true docker compose up --build
```

### Which registers are safe to profile

**Good candidates** — instantaneous physical quantities that genuinely track the sun:
irradiance (`1007`, `239`, `242`, `246`), active/apparent power (`4`, `254`, `258`),
string current (`6`), module/cell temperature (`1009`, `243`, `247`), and on the BESS
state of charge (`104`) and pack voltage (`101`).

**Leave these as `"random"`** — a smooth curve is actively wrong for them:

- **Enum registers** (`16`–`21`, `1016`–`1021`, `110`–`112`, `1110`–`1112`,
  device_3 `268/276/284/292`). Interpolating an enum along a bell curve marches the
  inverter Off → Startup → MPPT → Derating → Fault in lockstep with the sun.
- **Bitfield registers** (`22`–`31`, `1022`–`1031`, `113`–`115`, `1113`–`1115`,
  device_3 `241`, `267`). A value interpolated between 0 and 255 yields arbitrary flag
  combinations; a bitfield's bits are independent, which is the opposite of one smooth scalar.
- **Fault codes** (`9`, device_3 `275/283/291/299`) — discrete, same problem as enums.
- **Grid-side electricals** (`3` frequency, `1001`–`1003` phase voltages, device_3 `215`,
  `271/279/287/295`). Set by the grid, not the sun.
- **Cumulative counters** (`1010`, `1011`, device_3 `235`, `237`, `260`, `262`, and
  device_2's 32-bit `116`/`118`/`120`). Subtle one: the diurnal shape passes its
  midpoint *twice*, so a daily-energy counter would climb to noon and then **fall back**
  through the afternoon. A counter must rise monotonically and reset. Needs a separate
  monotonic shape — not yet implemented.
- **BESS unsigned magnitudes** (`102` charge/discharge current, `105` inverter output
  power). The BESS curve dips below its midpoint during the evening discharge, which would
  drive these toward `min` at exactly the moment they should peak.
