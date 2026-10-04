# Modbus TCP adapter

`ModbusAdapter` (`adapter.py`) serves the simulated site the way a site aggregator would: one TCP
server, one unit id, every device in its own 100-register chunk. It starts when the active site
config has `interfaces.modbus.enabled: true`.

## What it serves
- **Layout and values** come from `powerflow.point_standard`, which reads the PAE point standard
  (`docs/point-standard/*.csv`). That package holds every mapping and calculation; this adapter
  only serves the resulting register image. The layout table is in the point standard's README,
  `contracts/modbus/powerflow.registers.json` publishes it, and `GET /api/modbus/registers`
  returns it for the active site.
- **Refresh:** a background task checks the engine every 0.25 s. On a new step it advances the
  energy counters and rebuilds the image; when the active site changes it rebuilds the layout and
  restarts the counters.
- **Reads:** one shared pymodbus register block (`SimDevice` + `SimData`), so FC03 (holding) and
  FC04 (input) return the same values. The device's async `action` hook copies the current image
  into the requested range on every read. Addresses are zero-based.
- **Writes:** refused with exception 1 (ILLEGAL_FUNCTION). Setpoints are HTTP-only for now; a
  writable server would route writes through `PointRegistry.write` → `SetpointService`.

## Settings (`settings.py`)
`MODBUS_HOST` (0.0.0.0), `MODBUS_PORT` (502), `MODBUS_UNIT_ID` (1), `POINT_STANDARD_DIR`
(`docs/point-standard`). Compose publishes 502 as host port `POWERFLOW_MODBUS_PORT` (1502),
because mock-modbus owns host port 502 in the dev stack.

## Not used
The per-asset `ModbusMap`s stored with each site (`/api/sites/{site}/modbus-maps`, one unit id
per asset) predate this server and don't drive it.
