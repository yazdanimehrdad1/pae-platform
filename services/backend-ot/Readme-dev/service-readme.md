# PAE Backend OT — Service Notes

## Modbus Address Mode (`modbus_address_mode`)

### Background

pymodbus (used as the **client** in this service) sends raw **0-based PDU addresses** on the wire.
Most real Modbus devices (PLCs, relays, BESS units) document their registers using **1-based numbering** — so "register 1400" in the device manual is physically at PDU address 1399.

The `modbus_address_mode` field on a device bridges this gap.

### Modes

| Mode | Behaviour |
|------|-----------|
| `zero_based` | Configured address sent as-is to pymodbus. Use when the device (or mock) already uses 0-based addressing. |
| `one_based` | Subtract 1 from configured address before sending to pymodbus. Use for standard Modbus devices whose manuals use 1-based register numbers. |

### Mock server (`services/mock-modbus`)

> The mock server is a separate service in this monorepo (`services/mock-modbus`); backend-ot
> never imports its code. Wiring:
> - **Dev stack** (`make up` at the repo root): same compose network, `AGGREGATOR_MODBUS_HOST=mock-modbus`.
> - **Standalone** (`make -C services/backend-ot up`): `AGGREGATOR_MODBUS_HOST=host.docker.internal`,
>   i.e. mock-modbus's published host port (`make -C services/mock-modbus up`).
> - The dev seed's devices/points are built from mock-modbus's contract
>   (`contracts/modbus/mock-modbus.devices.json`), all `modbus_address_mode=one_based`.

The mock server uses `ModbusSlaveContext(zero_mode=False)` — the pymodbus default.

From its `app/settings.py`:

```python
# False (default): 1-based addressing — standard Modbus (Modbus Poll, most PLCs)
# True: 0-based addressing — use when clients send raw PDU addresses (e.g. pymodbus client)
zero_mode: bool = False
```

`zero_mode=False` means the **server adds 1** to every incoming PDU address before looking up in its datablock:

- Receives PDU address 1399 → adds 1 → looks up key **1400** → returns 105
- Receives PDU address 1400 → adds 1 → looks up key **1401** → returns 125

### How they work together

With device configured as `one_based` and mock data `{1400: 105, 1401: 125, 1402: 145}`:

| Step | `one_based` ✓ | `zero_based` ✗ |
|------|--------------|----------------|
| Configured address | 1400 | 1400 |
| PDU address sent | **1399** (1400 − 1) | **1400** |
| Mock looks up | key 1400 → 105 | key 1401 → 125 |
| Result for `dc_voltage` | **105** (correct) | **125** (dc_current's value — off by one) |

- Mock simulates a real Modbus device (1-based, like a PLC)
- This service uses `one_based` to bridge pymodbus's raw 0-based wire format to the device's 1-based register numbering
- After reading, addresses are re-keyed back to the configured values so device point lookups match correctly
