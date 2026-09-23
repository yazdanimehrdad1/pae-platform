# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## Overview

A **Modbus TCP register simulator**. It emulates industrial energy devices
(solar inverter, battery/BESS, utility-scale PV plant) by serving Modbus **holding
registers (FC 03)** and **input registers (FC 04)**. Addresses not in a device's map
return `default_register_value`. **Writes are silently ignored** — this is a read-only
mock.

Each register declares how its value is produced, via `RegisterSpec.type`:

- **`"random"`** (the default) — a fresh uniform draw from `[min, max]` on every read
  (`rng.randint(min, max) & 0xFFFF`).
- **`"profile_static"`** — the value is **looked up** by this register's *address* in a
  frozen table, [app/timeseries_data/pv_profile_static.py](app/timeseries_data/pv_profile_static.py).

Those are the only two. **Nothing is computed from a curve at read time** — a register
either draws randomly or reads a number someone wrote down. See "Profiling a register".

Stack: **pymodbus 3.5–3.6**, **pydantic v2**, **pydantic-settings**. Python **3.11**
(Docker image). Async throughout.

## Run it

Local (from repo root):

```bash
pip install -r requirements.txt
python -m app.server            # binds 0.0.0.0:502 by default
```

Port 502 is privileged on Linux/macOS — for local runs use a high port:

```bash
MODBUS_PORT=5020 python -m app.server
```

Container:

```bash
docker compose up --build       # or: make up
```

> Dependencies are managed with **pip + `requirements.txt`** (not uv). There is no
> `pyproject.toml`, lockfile, linter, or CI configured in this repo.

## Architecture — the read path

```
app/modbus_mock_data/device_N.py   →  exports DEVICE = DeviceSpec(...)
app/modbus_mock_data/__init__.py   →  auto-discovers every module's DEVICE into DEVICES
app/models.py                      →  DeviceSpec / RegisterSpec (pydantic v2, validated at import)
app/datastore.py                   →  build_device_blocks() → MockRegisterBlock.getValues() produces the value
app/profiles.py                    →  clock settings only: which row of the table a read lands on
app/server.py                      →  entry point; aggregator and/or per-device TCP servers

app/timeseries_data/pv_profile_static.py   →  frozen table read by type="profile_static" (IS in the read path)
app/timeseries_data/pv_day_generator.py  →  offline authoring tool: owns the sun curve, writes the table
```

- [app/models.py](app/models.py) — `RegisterSpec(name, type, width, unit, scale, min,
  max, enum_values, bit_flags)`,
  `DeviceSpec(unit_id, name, device_type, host, port, kw_max, holding_registers,
  input_registers)`, and the `DeviceType` enum. Both models use `extra="forbid"`;
  `RegisterSpec` rejects `min > max`, a band that does not fit its `width`, and a
  register that declares both `enum_values` and `bit_flags`. `device_type`
  is **required** — a device module that omits it fails at import rather than silently
  flat-lining. `kw_max` (nameplate kW) is optional, since an `ied` has no nameplate,
  but the timeseries generators require it. `StaticProfile` validates the frozen
  profile table (see "Timeseries data"). `RegisterSpec.name` is **required** and
  must be a snake_case identifier (`^[a-z][a-z0-9_]*$`), **unique across both register
  maps on a device** — names are identifiers, so a duplicate would make "read me
  `active_power`" ambiguous.
- [app/datastore.py](app/datastore.py) — `MockRegisterBlock` (a `ModbusSequentialDataBlock`)
  where `getValues` produces the value per read and `setValues` is a no-op;
  `build_device_blocks(...)` builds the holding + input blocks sharing one `random.Random(seed)`.
  **This is the only place the clock is read** — once per request, so a multi-register
  read is one coherent snapshot rather than samples smeared along the curve.
- [app/profiles.py](app/profiles.py) — `ProfileConfig` (timezone offset, day compression)
  and `simulated_hour_of_day(now, config)`. That is all: it answers *what time it is*,
  never what a value should be. Pure — the timestamp is passed in.
- [app/modbus_mock_data/__init__.py](app/modbus_mock_data/__init__.py) — discovery; a module
  without a `DEVICE` export is skipped, a `DEVICE` that isn't a `DeviceSpec` raises `TypeError`.
- [app/timeseries_data/](app/timeseries_data/) — day-long generated series. Separate concern
  from the register maps and **not wired into the read path** — see "Timeseries data" below.
- [app/server.py](app/server.py) — `_start_aggregator`, `_start_per_device`, `run_server`.

## How to add a device

Drop a new file `app/modbus_mock_data/device_4.py` exporting a `DEVICE`. No other
change is needed — it's auto-discovered, and its register map is validated at import
(fail-fast, so a bad map crashes startup rather than serving bad reads).

```python
from app.models import DeviceSpec, RegisterSpec

DEVICE = DeviceSpec(
    unit_id=4,                 # unique per device; how the aggregator addresses it
    name="my_device",
    device_type="pv",          # pv | bess | ied  — the only three permitted
    kw_max=3.0,                # nameplate kW; optional, but needed for timeseries
    host="0.0.0.0",
    port=5023,                 # only used in per-device mode
    holding_registers={        # band for unit 4: 300–399
        301: RegisterSpec(name="dc_bus_voltage", min=470, max=490),
        302: RegisterSpec(name="active_power", type="profile_static", min=0, max=600),
    },
    input_registers={          # band for unit 4: 1300–1399
        1301: RegisterSpec(name="module_temperature", min=90, max=110),
    },
)
```

`device_type` and every register's `name` are required. `type` defaults to `"random"`,
so omitting it gives the historical behaviour. A `profile_static` register also needs
its address present in that device's frozen table, or startup fails.

### Address bands — one 100-wide block per device, per register file

**Every device owns a fixed 100-address band in each of the two register files.** The
band is derived from `unit_id`, so a new device's addresses are decided for it:

```
holding band  =        (unit_id - 1) * 100   ->  0–99, 100–199, 200–299, 300–399, …
input band    = 1000 + (unit_id - 1) * 100   ->  1000–1099, 1100–1199, 1200–1299, …
```

| unit | device | holding band | in use | input band | in use |
|---|---|---|---|---|---|
| 1 | `device_1` | `0–99` | 1–31 | `1000–1099` | 1001–1031 |
| 2 | `device_2` | `100–199` | 101–123 | `1100–1199` | 1101–1115 |
| 3 | `device_3` | `200–299` | 201–299 | `1200–1299` | *(none — the real site defines no FC04 registers)* |
| 4 | *next device* | `300–399` | — | `1300–1399` | — |

Rules for staying inside the scheme:

- **A band is a hard ceiling, not a suggestion.** device_3 already fills 201–299. A
  device needing more than 100 holding registers needs a second unit_id, not a wider
  band — the whole point is that an address tells you which device it belongs to.
- **A 32-bit register consumes two addresses**, so budget `address + 1` inside the
  band as well.
- **Start at `base + 1`, never at the band's first address.** Only address `0` is
  genuinely unusable — under the default `ZERO_MODE=false` a client's wire address `N`
  reads dict key `N+1`, so no wire address can reach key `0`. Every band begins at
  `base + 1` anyway, so all six bands read the same way.
- **Holding and input are separate address spaces**, so a holding `104` and an input
  `1104` are unrelated. The 1000 offset on input bands is purely so a bare address in
  a log line or a ticket is unambiguous about which file it came from.
- Within a band, registers keep meaningful gaps (an undefined range, the low word of a
  32-bit point). Gaps are free — a band has far more room than any device uses.

### 32-bit registers (`width=32`)

Modbus has no 32-bit register: a 32-bit point is **two consecutive addresses**, high
word first. `RegisterSpec.width` (`16`, the default, or `32`) says which a register is.
One spec covers both addresses — you declare only the high one:

```python
116: RegisterSpec(name="lifetime_energy_charged", type="random", width=32, unit="Wh", scale=1.0, min=0, max=500_000_000),
# 117 is this register's low word. Do NOT declare it.
```

- `min`/`max` are the bounds on the **whole 32-bit number**, so a counter can hold a
  real range. A `width=16` register is capped at `-32768..65535`; declaring a wider
  band on one **fails at import** rather than silently wrapping (a `max` of 80000 used
  to be served as 14464).
- A read draws the value **once per request** and splits it, so the high and low words
  a client gets back always recombine to a number inside `[min, max]` — they are never
  two unrelated draws. Reading one word on its own still works; it is just half of a
  number.
- Declaring `address + 1` separately is rejected at startup, naming both registers.
- `width=32` and `type="profile_static"` are mutually exclusive: the frozen table holds
  16-bit values.

In use today: device_2 `116`/`118`/`120`/`122` (lifetime Wh counters, uptime, fault
timestamp) and device_3 `237`/`262`, the two energy totals whose real ranges never fit
a uint16.

**Naming convention:** snake_case, describing *what the register is* — the unit, scale
and engineering range stay in the trailing comment, which is different information.
device_3's names are the lower-cased point names from the site's real register map
(`poi_active_power_total`, `inv01_grid_voltage_ab`), so they round-trip against the
source CSV. Because names are unique per device, `{spec.name: address}` is a usable
lookup — that is the point of the field.

Existing devices for reference:

| file | unit | `device_type` | `kw_max` | derived from |
|---|---|---|---|---|
| `device_1.py` | 1 | `pv` | 3.0 kW | holding 4 active power W, caps at 2900 |
| `device_2.py` | 2 | `bess` | 10.0 kW | holding 105 inverter output W, caps at 10000 |
| `device_3.py` | 3 | `pv` | 3300.0 kW | holding 254 total AC power ×0.1 kW, caps at 33000 |

Nothing uses `ied` yet — it is there for meters, relays and controllers, which measure
the grid rather than generating.

### device_3 and its source register map

`device_3.py` is transcribed from a real operational site's export,
`PV_Asset_Mock_Modbus_Register_Map.csv` — POI meter, weather station, PV fleet
aggregates and four named inverters. Holding registers only; the real site defines no
FC04 input registers. Three things about that transcription matter before you compare
the file against the CSV:

- **Dict key = the CSV's `Offset` column + 201.** Two separate offsets are stacked
  here. The `+1` is the addressing base: under the default `zero_mode=False` a
  register sent as address `N` on the wire lands on dict key `N+1`, so a key is
  exactly the address you would type into a standard Modbus client. The `+200` is
  device_3's holding band (unit 3). CSV offset `0` is therefore key `201`, and offset
  `98` is key `299`. Without knowing this, a diff against the CSV looks like every
  address is wrong.
- **Most 32-bit points became single 16-bit registers.** 19 source points are
  int32/uint32 (two registers each). Each is kept at its *primary* offset only and the
  low word dropped — that is why the map has gaps at even addresses 202–236, and at
  255/257/259/261. The two exceptions are `237` and `262`, the energy totals whose
  ranges genuinely do not fit a uint16: they keep their true `width=32`, so `238` and
  `263` are their low words rather than gaps.
- **Some scales were rebased to fit uint16** — W→kW, A ×0.001→×0.1, Wh/kWh→MWh — to
  preserve the real magnitude. `PV_AVG_INVERTER_EFFICIENCY` additionally corrects a
  bug in the source CSV, whose 0.001 scale overflows uint16 at 100% (rescaled to 0.01).

## Configuration (env vars)

Set via environment (`env_prefix=""`, so the var name is the field name uppercased).
Defined in [app/settings.py](app/settings.py):

| Variable                 | Default   | Meaning                                                                 |
|--------------------------|-----------|-------------------------------------------------------------------------|
| `AGGREGATOR_ENABLED`     | `true`    | All devices on one server (`MODBUS_HOST:MODBUS_PORT`), addressed by `unit_id`. |
| `MODBUS_HOST`            | `0.0.0.0` | Aggregator bind address.                                                |
| `MODBUS_PORT`            | `502`     | Aggregator TCP port.                                                    |
| `PER_DEVICE_ENABLED`     | `false`   | Also run one server per device on its own `host`/`port` from the device file. |
| `DEFAULT_REGISTER_VALUE` | `0`       | Value for any address not in a device's map.                            |
| `LOG_LEVEL`              | `INFO`    | Python log level.                                                       |
| `RANDOM_SEED`            | *(empty)* | Integer seed for deterministic output; empty string ⇒ non-deterministic. |
| `ZERO_MODE`              | `false`   | Addressing base — see gotcha below.                                     |
| `PROFILE_TIMEZONE_OFFSET_HOURS` | `0.0` | Offset on top of UTC deciding where solar noon falls. No DST.       |
| `PROFILE_DAY_MINUTES`    | `1440.0`  | Real minutes per simulated day. `1440` = real time; set low to demo.    |

At least one of `AGGREGATOR_ENABLED` / `PER_DEVICE_ENABLED` must be true, or the
server exits with an error. Both may run at once.

The two `PROFILE_*` vars only affect `type="profile_static"` registers, and they only
decide **which row** of the frozen table a read lands on — never the value, which is a
literal. `PROFILE_DAY_MINUTES=2` walks a whole day in two minutes.

## Conventions

- `from __future__ import annotations` at the top of every module; full type hints on
  all signatures.
- pydantic v2 models with `ConfigDict(extra="forbid")`; config only through the
  `Settings` model — no inline `os.environ` reads.
- `asyncio` throughout (`async def`, `asyncio.gather`, `asyncio.run`).
- One named logger: `logging.getLogger("mock_modbus")`.
- `snake_case`; private module helpers prefixed `_`.

## Gotchas

- **Aggregator vs per-device.** Default is aggregator only: one server on
  `MODBUS_PORT`, clients pick the device via `unit_id` (1/2/3). Per-device mode puts
  each device on its own port (5020/5021/5022) — enable with `PER_DEVICE_ENABLED=true`.
- **`ZERO_MODE`.** `false` (default) = 1-based addressing — standard Modbus (Modbus
  Poll, most PLCs). `true` = 0-based raw PDU addressing (e.g. the pymodbus client). If
  reads come back as the default value when you expect data, this is the usual cause.
  It also produces a subtler failure: with `ZERO_MODE=false`, a **raw-socket** client
  that puts address `N` on the wire reads the register defined at `N+1`, so you get
  plausible-looking values from the *neighbouring* register rather than an obvious zero.
  Verified after the address rebase, raw frames to device_1 with `ZERO_MODE=false`:
  wire `2` returned 4993–5008 (register `3`, `grid_frequency`), wire `3` returned 1000
  (register `4`, `active_power`), wire `4` returned 256 (register `5`,
  `inverter_temperature`) — each one register high. Use `ZERO_MODE=true` when driving
  the server with raw frames. This is also why no band starts at address `0`: reaching
  key `0` would need wire address `-1`, so a register there would be dead under the
  default.
- **`RANDOM_SEED=""`** (empty) means non-deterministic; set an integer for repeatable
  reads. It governs `type="random"` registers only. `profile_static` registers touch
  no RNG at all — they are a pure function of the clock, so they repeat exactly given
  the same timestamp regardless of seed.
- **Writes are ignored** (`setValues` is a no-op).
- The `tests/test_server.py` script is a standalone raw-socket smoke test, not a pytest
  suite, and its hardcoded addresses predate the current device maps.

## Timeseries data

[app/timeseries_data/](app/timeseries_data/) generates a **whole day of correlated plant
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

[app/timeseries_data/pv_day_generator.py](app/timeseries_data/pv_day_generator.py) — one day of PV
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

**The table is a pydantic model**, `StaticProfile` in [app/models.py](app/models.py) —
deliberately just types: `interval_minutes: int` and `rows: dict[str, dict[int, int]]`,
nothing else. Pydantic checks the shape for free, so a non-integer address or value is
rejected at import. No custom validators, no methods.

The behaviour lives in [app/datastore.py](app/datastore.py) instead:

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
`_static_profile_for` in [app/server.py](app/server.py). Today only `pv` has one.

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

## Known issue

`make up` uses `docker network create shared-network`, but
[docker-compose.yaml](docker-compose.yaml) expects an **external** network named
`pae-shared-network`. The names don't line up — create the network compose wants with
`docker network create pae-shared-network` before `docker compose up`.
