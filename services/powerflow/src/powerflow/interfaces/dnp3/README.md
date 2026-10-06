# DNP3 outstation adapter (placeholder)

Not implemented yet. The package only exists so the adapter can be added later without
touching the simulation core.

## Intended scope
- A `ProtocolAdapter` (see `interfaces/base.py`) named `dnp3`, registered in the app's
  `AdapterRegistry` and started when the site config has `interfaces.dnp3.enabled: true`.
- An outstation whose point layout comes from the PAE point standard, like the Modbus server
  (`powerflow.point_standard`): a DNP3 index per standard point, values from the same resolvers.
- **Readable points map to DNP3 types:**
  - R `float32` points → analog inputs.
  - `enum16` / `bitfield16` status points → analog or binary inputs.
  - `step_id` → a counter.
- **Writable points:** RW setpoints map to analog outputs (and `mode_cmd` to a CROB or an analog
  output). Writes call `PointRegistry.write(...)`, so they're validated and clamped exactly like
  HTTP setpoints.
- **Event classes and deadbands** come from the map file.
- **Library:** a DNP3 library (for example `dnp3py`/OpenDNP3 bindings). Adding one needs the
  user's OK.

## Not in scope
- **Direct access to models or the solver:** the adapter never touches asset models or the
  solver.
- **Engine control:** start/stop/config stay HTTP-only.
