# Modbus TCP adapter (placeholder)

Not implemented yet. The package only exists so the adapter can be added later without
touching the simulation core.

## Intended scope
- A `ProtocolAdapter` (see `interfaces/base.py`) named `modbus`, registered in the app's
  `AdapterRegistry` and started when the site config has `interfaces.modbus.enabled: true`.
- It serves one Modbus device per simulated asset, each at its own unit ID (and optionally its
  own port), as described by the **active site's** maps (stored in the database, editable at
  `/api/sites/{site}/modbus-maps`). That is how real site devices appear to an EMS.
- The map format is `powerflow.points.modbus_map.ModbusMap`; its JSON Schema is at
  `GET /api/schemas/modbus-map`. The maps are stored per site in the database, and every
  default site ships with a map for each asset (the default layout from `default_map()`).
  Each entry binds a point name from the protocol-neutral point list (`powerflow.points`) to a
  register type, address, data type, word order and scale (engineering value = raw × scale).
- **Reads:** register values come from `PointRegistry.read("<asset>.<point>")`, and are refreshed
  each step.
- **Writes:** holding registers and coils go to `PointRegistry.write(...)`. That goes through
  `SetpointService`, so Modbus setpoints are validated and clamped exactly like HTTP ones.
- A 32-bit value spans two registers, in the map's `word_order`.
- **Library:** likely `pymodbus` (already used by backend-ot). Adding it needs the user's OK.

## Not in scope
- **Direct access to models or the solver:** the adapter never touches asset models or the
  solver.
- **Engine control:** start/stop/config stay HTTP-only.
