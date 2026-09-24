# Authoring mock devices

> Reference for `app/modbus_mock_data/device_N.py`. The step-by-step procedure is the
> `add-mock-device` skill (`.claude/skills/add-mock-device/SKILL.md`); conventions here are
> enforced by `tests/test_device_maps.py`.

## Adding a device

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
