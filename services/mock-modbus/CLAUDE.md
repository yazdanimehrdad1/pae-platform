# mock-modbus

**DEV-ONLY.** Stands in for on-site OT devices during development. It must never appear
in a production manifest (k8s, overlays, prod compose). Owned here: the simulator and its
device register maps. Not owned: anything backend-ot does with the values — backend-ot
reaches this service over Modbus TCP only and never imports its code.

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
either draws randomly or reads a number someone wrote down. See
[docs/profiles-and-timeseries.md](docs/profiles-and-timeseries.md).

Stack: **pymodbus 3.5–3.6**, **pydantic v2**, **pydantic-settings**. Python **3.11**
(Docker image). Async throughout.

## Commands

Run from the repo root as `make -C services/mock-modbus <target>` (or `make <target>` here).
Same Makefile on Windows (recipes run in Git for Windows' sh). **uv only** — deps are pinned in
`uv.lock`; add with `uv add` / `uv add --dev`. No type checker is configured yet.

- `make install` — uv sync → `.venv`.
- `make test` — pytest. Starts the real server (`python -m app.server`) on a free localhost
  port with pinned settings, reads every declared register over raw Modbus TCP, and checks
  device-file conventions. No Docker. `TEST_PATH=...` to narrow.
- `make lint` / `make lint-fix` — ruff (same rule set as backend-ot).
- `make run` — server on the host, port `RUN_PORT` (default 5020; 502 is privileged on Linux/macOS).
- `make up` / `make down` / `make logs` — standalone container on host port 502 (override with
  `MOCK_MODBUS_PORT`; `make up` builds and waits for healthy). `ZERO_MODE=false` is pinned in
  `compose.yaml` because the contract's 1-based numbering depends on it. The whole platform
  runs from the repo root (`make up`, see the `run-platform` skill).
- `make contract` — regenerate `contracts/modbus/mock-modbus.devices.json` (the published
  register map). **Run it after any device/register change**; `make test` fails while it's stale.

## Contract provided

`contracts/modbus/mock-modbus.devices.json` — every device (unit_id, type) and register
(file, 1-based address, width, sign, scale, unit, enum/bit labels), generated from the device
files by `app/contract.py`. backend-ot builds its dev seed from it, so the historian polls
exactly what this simulator serves. Consumers read the JSON; nobody imports this code.

## Where the detail lives

- Adding or changing a device / register → **`add-mock-device` skill**, reference in
  [docs/device-authoring.md](docs/device-authoring.md) (address bands, 32-bit registers, naming,
  device_3's source map).
- `type="profile_static"`, the frozen table, the day generator, which registers are safe to
  profile → [docs/profiles-and-timeseries.md](docs/profiles-and-timeseries.md).

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
  profile table (see docs/profiles-and-timeseries.md). `RegisterSpec.name` is **required** and
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
  from the register maps and **not wired into the read path** — see docs/profiles-and-timeseries.md.
- [app/server.py](app/server.py) — `_start_aggregator`, `_start_per_device`, `run_server`.

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
  Poll, most PLCs). `true` = 0-based raw PDU addressing. **Keep `false` for the platform:**
  backend-ot's devices use `modbus_address_mode=one_based` and subtract 1 before sending.
  If reads come back as the default value when you expect data, this is the usual cause.
  It also produces a subtler failure: with `ZERO_MODE=false`, a **raw-socket** client
  that puts address `N` on the wire reads the register defined at `N+1`, so you get
  plausible-looking values from the *neighbouring* register rather than an obvious zero.
  Verified after the address rebase, raw frames to device_1 with `ZERO_MODE=false`:
  wire `2` returned 4993–5008 (register `3`, `grid_frequency`), wire `3` returned 1000
  (register `4`, `active_power`), wire `4` returned 256 (register `5`,
  `inverter_temperature`) — each one register high. Raw-frame clients (like
  `tests/modbus_frames.py`) must send `key - 1`; see `wire_address_for`. This is also why no band starts at address `0`: reaching
  key `0` would need wire address `-1`, so a register there would be dead under the
  default.
- **`RANDOM_SEED=""`** (empty) means non-deterministic; set an integer for repeatable
  reads. It governs `type="random"` registers only. `profile_static` registers touch
  no RNG at all — they are a pure function of the clock, so they repeat exactly given
  the same timestamp regardless of seed.
- **Writes are ignored** (`setValues` is a no-op).
- Tests derive every expectation from the device files (`DEVICES`), so a new device or
  register is covered automatically — don't hardcode addresses in tests.
