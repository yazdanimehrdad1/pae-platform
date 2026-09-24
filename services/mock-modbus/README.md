# Mock Modbus TCP Server

Modbus TCP register simulator. It emulates industrial energy devices (solar
inverter, battery/BESS, utility-scale PV plant) and serves **holding registers (FC 03)**
and **input registers (FC 04)**. Unmapped addresses return `DEFAULT_REGISTER_VALUE`.
Writes are ignored (read-only mock).

Each register picks how its value is produced:

- **`type="random"`** (the default) — a fresh value within its `[min, max]` band on
  every read.
- **`type="profile_static"`** — the value is **looked up by register address** in a
  frozen table, `app/timeseries_data/pv_profile_static.py` (288 rows, five-minute
  resolution). A PV device's output then sits at zero overnight and peaks at solar
  noon instead of jumping around at 3 a.m.

Those are the only two — nothing is computed from a curve at read time.

`device_1` uses both: **14 registers `profile_static`** (power, currents, irradiance,
temperatures…) and **41 `random`** — grid frequency, phase voltages, fault codes,
enums, bitfields and the energy counters, for which a smooth daily shape is simply
wrong. `device_2` and `device_3` are still fully random.

**Dev-only** — never deployed to production. Built on pymodbus 3.5–3.6, pydantic v2, and pydantic-settings. Python 3.11, managed with uv.

## Quick start

From the monorepo root (uv manages the venv; see `uv.lock`):

```bash
make -C services/mock-modbus install      # uv sync
make -C services/mock-modbus test         # pytest: starts the server itself, no Docker
make -C services/mock-modbus run          # host run on port 5020 (RUN_PORT=... to change)
make -C services/mock-modbus up           # container on host port 502 (builds, waits for healthy)
```

The server listens on port **502** by default and serves 3 devices.

## Run modes

- **Aggregator** (default, `AGGREGATOR_ENABLED=true`): one TCP server on
  `MODBUS_HOST:MODBUS_PORT`; clients select a device by its `unit_id` (1/2/3).
- **Per-device** (`PER_DEVICE_ENABLED=true`): each device also gets its own server on
  its own port (5020 / 5021 / 5022). Both modes may run at once.

## Environment variables

| Variable                 | Default   | Description                                                        |
|--------------------------|-----------|--------------------------------------------------------------------|
| `AGGREGATOR_ENABLED`     | `true`    | Serve all devices on one port, addressed by `unit_id`.             |
| `MODBUS_HOST`            | `0.0.0.0` | Aggregator bind address.                                           |
| `MODBUS_PORT`            | `502`     | Aggregator TCP port.                                               |
| `PER_DEVICE_ENABLED`     | `false`   | Also serve each device on its own host/port.                       |
| `DEFAULT_REGISTER_VALUE` | `0`       | Value for addresses not in a device's register map.                |
| `LOG_LEVEL`              | `INFO`    | Python log level.                                                  |
| `RANDOM_SEED`            | *(empty)* | Integer seed for deterministic output; empty ⇒ non-deterministic.  |
| `ZERO_MODE`              | `false`   | `false` = 1-based (Modbus Poll/PLCs); `true` = 0-based (pymodbus).  |
| `PROFILE_TIMEZONE_OFFSET_HOURS` | `0.0` | Offset on top of UTC for where solar noon falls. No DST.      |
| `PROFILE_DAY_MINUTES`    | `1440.0`  | Real minutes per simulated day. `1440` = real time.                |

The two `PROFILE_*` variables only affect `profile_static` registers, and they only
decide which row of the frozen table a read lands on — never the value itself.

See [.env.example](.env.example) for a copyable template; `app/settings.py` loads `.env` from
this directory, and real environment variables override it.

## Register definitions

Devices live in `app/modbus_mock_data/` — one file per device (`device_1.py`,
`device_2.py`, `device_3.py`), each exporting `DEVICE = DeviceSpec(...)` with a
required `device_type`. Every register carries a required snake_case `name`
(`active_power`, `solar_irradiance`, `inv01_grid_voltage_ab`), unique within its
device, so a register says what it represents rather than relying on a comment. To
add a device, drop a new `device_N.py` into that folder;
it's auto-discovered and validated at startup. See [docs/device-authoring.md](docs/device-authoring.md)
for a device template and address bands, [CLAUDE.md](CLAUDE.md) for the architecture, and
[docs/profiles-and-timeseries.md](docs/profiles-and-timeseries.md) for which registers are worth profiling.

To watch a profile curve without waiting for noon, compress the day:

```bash
PROFILE_DAY_MINUTES=2 ZERO_MODE=true docker compose up --build
```

## Timeseries data

`app/timeseries_data/` holds a matched pair covering one day of plant behaviour —
power, irradiance, temperatures and wind all driven by one sun.

**`pv_day_generator.py`** is an **offline authoring tool** — it owns the sun curve
and *computes* a day at **5-minute intervals (288 samples)**, scaled from a nameplate
in kW. Use it to write or retune the static table. Nothing at runtime calls it, and it
has no CLI — it is a library with one entry point:

```python
from app.timeseries_data.pv_day_generator import generate_pv_day

samples = generate_pv_day(kw_max=3300.0, seed=42)   # 288 PvSample
```

**`pv_profile_static.py`** is a *frozen* table of 288 rows keyed by `"HH:MM"` then by
**register address** — and this one **is** on the read path: `device_1`'s
`profile_static` registers read straight out of it. Edit a number and that is exactly
what the register reports at that time.

```python
PV_PROFILE_STATIC = StaticProfile(
    interval_minutes=5,
    rows={
        "13:00": {1403: 2604, 2006: 1100, 2007: 427, 2008: 639},
        "15:00": {1403: 2458, 2006: 1001, 2007: 450, 2008: 621},
    },
)
```

It is a plain pydantic model (`StaticProfile` — two typed fields, nothing else), so
non-integer addresses or values are rejected at import. The lookup and the
"every row supplies this address" check live in `app/datastore.py`.

```
time          kw      ghi      poa  ambient   module   wind
12:25      2.349    906.1   1042.1     25.0     59.0   4.14
12:30      2.176    828.7    953.0     25.1     56.2   3.74
...
peak 2.349 kW at 12:25 (78.3% of nameplate) — daily yield 20.6 kWh (6.87 kWh/kW)
```

Each sample carries `timestamp, kw, irradiance_w_m2, poa_irradiance_w_m2,
ambient_temp_c, module_temp_c, wind_speed_m_s`. Peak output lands below nameplate
because hot modules derate, ambient temperature peaks mid-afternoon rather than at
solar noon, and cloud persists across samples instead of flickering. See
[docs/profiles-and-timeseries.md](docs/profiles-and-timeseries.md) for the full model.

## Testing

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("localhost", port=5020)
client.connect()

# Device 1 (solar inverter) exposes holding registers starting at 1400.
result = client.read_holding_registers(1400, count=4, slave=1)
print(result.registers)

client.close()
```

> Note: with default `ZERO_MODE=false` (1-based), request the register address as-is
> (e.g. `1400`). If your client sends 0-based PDU addresses, set `ZERO_MODE=true`.

There is also a standalone raw-socket smoke test:
`python tests/test_server.py --host localhost --port 5020 --unit-id 1`
(not a pytest suite; some hardcoded addresses predate the current device maps).
