---
name: add-mock-device
description: Add a new simulated Modbus device to mock-modbus, or add/change registers on an existing one (holding or input, 16- or 32-bit, enum, bitfield, random or profile_static). Use for requests like "add a BESS to the mock", "add a voltage register to device 2", "mock this register map", "make register 1007 follow the sun".
---

# Add or change a mock Modbus device

Devices are Python modules in `app/modbus_mock_data/device_N.py`, each exporting
`DEVICE = DeviceSpec(...)`. They are auto-discovered at import; nothing else needs
registering. The full reference, with a template, the address-band table, 32-bit rules
and naming, is in `docs/device-authoring.md`. Read it before writing registers.

## Rules (enforced by `tests/test_device_maps.py`; violating one fails `make test`)

- **unit_id is unique** and decides the device's address bands:
  holding `(unit_id-1)*100 + 1 … +99`, input `1000 + (unit_id-1)*100 + 1 … +99`.
  A device needing more than 99 registers in a file gets a second unit_id, never a wider band.
- **Register keys are the 1-based addresses a standard Modbus client types** (the server
  runs `ZERO_MODE=false`). Never use the band's first address.
- **32-bit (`width=32`)**: declare only the high word; `key + 1` is its low word, must stay
  inside the band, and must not be declared. `min`/`max` bound the whole 32-bit number.
  `width=32` can't be `profile_static`.
- **Every register states `type=` explicitly** (`"random"` or `"profile_static"`), even
  though `"random"` is the default.
- `name` is snake_case and unique across both maps on the device. The unit, scale and
  range stay in the trailing comment.
- `device_type` is required: `pv` | `bess` | `ied`. `kw_max` is needed only if the timeseries
  generators will be used.

## Procedure — new device

1. Pick the next unused `unit_id` (`grep -n unit_id app/modbus_mock_data/device_*.py`),
   and name the file `device_<unit_id>.py`.
2. Copy the template in `docs/device-authoring.md` ("Adding a device"). Set `host="0.0.0.0"`
   and `port=5019 + unit_id` (the per-device mode port; 5020, 5021 and so on).
3. Add registers inside the bands, following the rules above. Enum registers get
   `enum_values`, bitfields get `bit_flags`, and never both.
4. Only use `type="profile_static"` if the device type has a frozen table (today only `pv`,
   via `_static_profile_for` in `app/server.py`) and the address is in **every** row of it.
   Read `docs/profiles-and-timeseries.md` ("Which registers are safe to profile") first.
   Enums, bitfields, fault codes, counters and grid-side values must stay `random`.
5. Update the "Existing devices" and band tables in `docs/device-authoring.md`.

## Procedure — change an existing device

Edit its `device_N.py` in place, staying inside that device's bands. Moving an address
changes what every consumer reads, so treat it as a contract change. **Renaming** a
register: backend-ot's seeder matches existing points by name, so re-seeding an existing
dev database adds a point under the new name and leaves the old one at the same address.
Delete the old point, or re-create the dev stack's data, after a rename.

## Publish the change

Run `make -C services/mock-modbus contract`. That regenerates
`contracts/modbus/mock-modbus.devices.json`, the register map other services consume.
Commit the regenerated file with the device change; `make test` fails while it's stale.

## Done when

- `make -C services/mock-modbus lint` passes.
- `make -C services/mock-modbus test` passes. It checks the band, type and build rules
  statically, then starts the real server and reads **every** declared register over
  Modbus TCP, checking each value against its spec. It also checks that the committed
  contract is current. New registers are covered automatically; don't hardcode
  addresses in tests.
- `make -C services/backend-ot test` passes. backend-ot's seed tests build from the
  contract and fail if a register can't be mapped to a device point.

## backend-ot picks it up automatically

backend-ot's dev seed (`services/backend-ot/tests/seed_db/mock_modbus_seed.py`) builds one
device per mock device and one point per register **from the contract**, so there is
nothing to hand-edit there. Re-seed a running stack with
`make -C services/backend-ot seed-db`. If a new register kind can't be mapped (e.g. a
new data type), extend `point_data_type` there and its tests in
`services/backend-ot/tests/unit/seed/`, following backend-ot's CLAUDE.md.
