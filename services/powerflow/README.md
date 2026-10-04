# powerflow: microgrid power flow simulator

A grid-connected site you can drive like a real one. The EMS writes setpoints. Every step
(1 s by default, in real time) the simulator:
1. applies each asset's limits;
2. solves the balanced, positive-sequence, steady-state power flow (pandapower Newton-Raphson);
3. publishes a measurement snapshot.

Interfaces: HTTP (always on) and a read-only Modbus TCP server that serves the site as one
aggregator using the PAE point standard (see [Modbus server](#modbus-server)). DNP3 is a placeholder.

```
[utility source] ─ grid impedance (S_sc, X/R) ─ [POI] (─ optional POI line)
[POI] ─ MV collector bus(es) ─ step-up transformer ─ [LV] ─ BESS / PV inverter
[POI | collector] ─ (optional transformer) ─ site load (profile)
```

## Run
- **With the platform:** `make up` at the repo root builds and starts powerflow and its Postgres with the rest of the dev stack. Then open http://localhost:8020/docs.
- **Alone, in Docker:** `make down` at the root first, then `make -C services/powerflow up`. That builds the image and starts powerflow plus `powerflow-postgres`, waiting until both are healthy.
- **On the host:** start the database (for example `make -C services/powerflow up`, then stop only the app container), or point `DATABASE_URL` at any Postgres. Then run `make -C services/powerflow run`.
- **First start:** on an empty database, powerflow seeds the shipped defaults from `site_config/` and runs the default active site, `reference_2bess_1pv`. That site is 12.47 kV with a 100 MVA / X/R 5 grid, 2 × 2.5 MW / 10 MWh BESS, 5 MWac PV (all on 12.47/0.48 kV step-ups) and a 3 MW peak load, with a feeder meter on each step-up's 12.47 kV side.
- **Choosing the site:** switch with `POST /api/sites/{name}/activate`. For one run only, set `ACTIVE_SITE`.

```sh
curl -X PUT localhost:8020/api/assets/bess/bess1/setpoint \
     -H 'Content-Type: application/json' -d '{"p_kw": 2000, "q_kvar": 0, "mode": "pq"}'
curl localhost:8020/api/measurements/poi
curl 'localhost:8020/api/measurements/history?fields=poi.meter.p_kw,bess.bess1.soc_pct&format=csv'
```

**Postman:** import `postman/powerflow.postman_collection.json` (File → Import). It has one request per endpoint,
grouped by area, with example bodies and a `{{baseUrl}}` variable (default `http://localhost:8020`).
`make -C services/powerflow postman` regenerates it after a route change; `make test` fails while it's stale.

## Sign conventions and units
| Quantity | Positive means |
|---|---|
| BESS / PV P, Q | injecting into the network (generator convention). BESS P < 0 = charging |
| Load P, Q | consuming (Q > 0 lagging) |
| POI P, Q | export to the utility (P < 0 = import) |
| Feeder meter P, Q | flowing toward the MV bus (out of the transformer's HV terminal, after its losses) |
| Transformer P, Q | flowing toward the grid (LV → HV). `p_lv_kw` enters at LV, `p_hv_kw` leaves at HV |
| pf | \|P\|/S, signed with Q in the element's own convention |

Units: kW, kvar, kVA, kWh, kV (line-to-line), pu where noted, seconds.

## Configuration storage
| What | Where | API |
|---|---|---|
| Site configs (`SiteConfig`) | Postgres `sites` (JSONB) | `/api/sites`, `/api/sites/{name}` (+ `/activate`) |
| Modbus maps, one per asset per site | Postgres `modbus_maps` (JSONB; deleted with their site) | `/api/sites/{site}/modbus-maps/{asset}` |
| The active site | Postgres `app_state` | `POST /api/sites/{name}/activate` |
| Profile scenarios | **CSV files** in `site_config/profiles/{load,pv}/` (not in the database yet) | `/api/profiles/{load\|pv}/{scenario}` |
| JSON Schemas | generated from code | `/api/schemas/{site-config,modbus-map}` |

- **Database:** powerflow owns its own Postgres, `powerflow-postgres` (host port 5436), set by `DATABASE_URL`. The SQL migrations in `src/powerflow/storage/migrations/` run at startup.
- **Writes:** every write is validated before it's stored.
- **Shipped defaults** (read-only seed data):
  - `site_config/sites/*.json`, `site_config/modbus_maps/<site>/*.json` and `site_config/active.json`.
  - They're imported into an empty database at startup.
  - `POST /api/defaults/restore` re-imports them. Items already stored are kept; `?overwrite=true` replaces them, and the simulation must be stopped for that.
  - `GET /api/defaults` lists them.
  - The API never writes these files.
- **Profile edits:** `PUT /api/profiles/...` writes the CSV files. In the container they live on the `powerflow-profiles` volume, which Docker seeds from the image; on the host they go straight into the repo folder.
- **Resetting:** `make -C services/powerflow down-all` deletes the database and profile volumes, which resets everything to the shipped defaults. It's destructive, so only run it on purpose.
- **Regenerating the shipped files:**
  - `make -C services/powerflow profiles` regenerates the profile CSVs.
  - `make -C services/powerflow modbus-maps` regenerates the default map files. The database is untouched: use restore with overwrite to load them.

## Site config (JSON)
One Pydantic model (`SiteConfig`) validates the default site files, `PUT /api/sites/{name}`,
what's read back from the database, and `GET /api/schemas/site-config`. Unknown keys are
rejected. The sections are:
- **`simulation`:** `step_s`, `start_time` (sim time starts here and advances 1:1 with wall-clock), `autostart`, `test_mode` (enables manual stepping), `seed`, `history_size`.
- **`grid`:** `vn_kv` (12.47), `vm_pu`, `sc_mva`, `x_r`. The grid is modelled as a source behind |Z| = V²/S_sc.
- **`poi.line`:** an optional POI cable. **`collectors`:** MV buses, each with an optional feeder line, otherwise tied to the POI bus.
- **`bess[]`:**
  - `inverter`: `s_rated_kva`, `p_discharge_max_kw`, `p_charge_max_kw`, `v_lv_kv`, `priority` (`p`|`q`), `ramp_kw_per_s`.
  - `battery`: `capacity_kwh`, SOC min/max/initial, `efficiency` (`charge`+`discharge`, or `round_trip`, split as √η), `aux_load_kw`.
  - `transformer`: `s_rated_kva`, `vn_hv_kv`, `vn_lv_kv`, `z_pct`, `x_r`, `no_load_loss_kw`, `i0_pct`.
- **`pv[]`:** `dc_kwp`, `loss_factor`, `inverter` (`s_rated_kva`, `p_max_kw`), `availability` (`source`: `ac_kw` | `irradiance`, plus a profile `scenario` from `profiles/pv/`, `scale` and `loop`), `transformer`.
- **`loads[]`:** `bus` (`poi` or a collector id), `profile` (`scenario` from `profiles/load/`, `scale`, `loop`), optional `noise` (% std, seeded), optional `transformer`.
- **`meters[]`:** feeder meters, each `{id, name?, transformer}`. `transformer` is the BESS, PV or load (with a transformer) whose transformer is metered on its HV side, between the MV bus and the transformer. A meter has no impedance: it reads the transformer's HV-terminal P/Q/I and the MV bus voltage.
- **`interfaces`:** `http` is always on; `modbus` starts the Modbus server (enabled on `reference_2bess_1pv`); `dnp3` isn't implemented yet, so enabling it only logs a warning.

Validation also checks:
- ids are unique and every reference points at something that exists;
- a meter's `transformer` is a BESS, PV or load that has a transformer, with at most one meter per transformer;
- each transformer's HV rating matches the grid and its LV rating matches the inverter, within 1 %;
- SOC min < max, and the initial SOC lies within them;
- each inverter's S rating is at least its P rating;
- every profile scenario the site names exists (checked when a site is saved).

**Profiles (CSV)**
- **Columns:** a `timestamp` column (ISO 8601; naive = UTC) and the value columns.
  - Load: `p_kw,q_kvar` or `p_kw,pf`.
  - PV: `p_kw` (the ac_kw source) and/or `ghi_wm2` (the irradiance source). The stored scenarios have both, for a 5 MWac / 6.5 MWp plant.
- **Interpolation and looping:** values are linearly interpolated. With `loop`, the profile repeats every (span + one sample interval); without it, the first and last values hold.
- **Editing at runtime:** `PUT /api/profiles/{load|pv}/{scenario}` with a `text/csv` body saves a scenario. Active-site assets that use it pick it up on the next step, even while running. Their configured `scale` and `loop` still apply.

## Asset models (pure Python, `src/powerflow/models/`)
- **BESS**, applied in this order:
  1. **Mode:** `offline` forces 0 at once; `idle` targets 0.
  2. **Static limits:** the P rating (`P_LIMIT`), then the S circle with P- or Q-priority (`S_LIMIT`).
  3. **Ramp** (`RAMP_LIMIT`).
  4. **SOC:** P is limited so SOC lands exactly on its limit (`SOC_LIMIT`). The BMS limit wins over the ramp.
  5. **Final S check:** Q is trimmed to fit the S circle.

  SOC integrates the actual P: discharging draws P/η_d from the cells, charging stores |P|·η_c. The aux load is drawn from the LV bus.
- **PV:**
  1. Available P comes from the profile (AC kW, or dc_kwp·G/1000), less losses, clipped at `p_max_kw` (`CLIPPED`).
  2. Actual P = min(available, curtailment) (`CURTAILED`).
  3. The S circle: Q mode uses the priority; PF mode scales P and Q together so the pf holds.
- **Load:** profile × scale, with optional Gaussian noise. The noise is seeded per (seed, step), so a run is deterministic.

## Engine
- **Real time:** tick k is due at anchor + k·step_s. If a step overruns, the missed ticks are skipped (`step_id` jumps and the skipped time is integrated as one longer step), `overrun_count` increments and a warning is logged.
- **States:** `start`, `pause` (resuming continues sim time without a jump), `stop` (keeps state; required for `PUT /config`), `reset` (initial state, empty history).
- **Test mode:** `POST /api/sim/step?count=N` exists only with `test_mode: true` and while not running. It is used for long-horizon tests.
- **Non-convergence:** the last good values are republished with `converged: false`, SOC doesn't advance, and `nonconverged_count` increments. The loop keeps running.
- **Determinism:** the same config, profiles, seed and setpoint sequence give the same snapshots.

## HTTP API (`/api`; OpenAPI at `/docs`)
| Area | Endpoints |
|---|---|
| Simulation | `POST sim/start`, `sim/pause`, `sim/stop`, `sim/reset`, `sim/step?count=N` · `GET sim/status` |
| Active config | `GET config` · `GET config/schema` |
| Sites | `GET sites` · `GET`/`PUT`/`DELETE sites/{name}` · `POST sites/{name}/activate` (while stopped) |
| Modbus maps | `GET sites/{site}/modbus-maps` · `GET`/`PUT`/`DELETE sites/{site}/modbus-maps/{asset}` (e.g. `pv.pv1`, `poi.meter`) |
| Profiles | `GET profiles` · `GET`/`PUT`/`DELETE profiles/{load\|pv}/{scenario}` (text/csv; DELETE refused while a site uses it) |
| Schemas | `GET schemas` · `GET schemas/{name}` (`site-config`, `modbus-map`; read-only) |
| Defaults | `GET defaults` · `POST defaults/restore?overwrite=` |
| Assets | `GET assets` (includes `meters`) · `GET assets/{bess,pv,load}/{id}` · `PUT assets/{bess,pv}/{id}/setpoint` |
| Points | `GET points` · `GET points/{name}` |
| Measurements | `GET measurements/latest`, `measurements/poi` · `GET measurements/history?from=&to=&fields=&format=json\|csv` |
| Modbus | `GET modbus/registers` (the Modbus server's register layout for the active site) |
| Service | `GET health`, `GET version` |

**Setpoints**
- **Partial updates:** omitted fields keep their value.
- **Invalid values → 422:** for example a non-number, an unknown mode, both `p_limit_kw` and `p_limit_pct`, or |pf| < 0.8.
- **Out-of-range values** are clamped to the static limits. The response's `accepted`, `clamped` and `flags` report what was applied.
- **Dynamic limits** (SOC, ramp) show in each measurement's `limit_flags`.

**Status codes:** 404 for an unknown asset or point; 409 for the wrong engine state or for no data yet.

**Missed steps:** every snapshot carries `step_id`, so a poller can detect missed steps and backfill from `history`.

## Points (protocol-neutral, `src/powerflow/points/`)
- **Names:** `<asset_type>.<asset_id>.<point>`, for example `bess.bess1.soc_pct`, `pv.pv1.p_limit_kw`, `poi.meter.p_kw`, `meter.m_bess1.p_kw` (a feeder meter, by meter id) and `site.sim.step_id`.
- **Point attributes:** each point has a description, unit, data type, access (R/RW), source (measurement, setpoint, nameplate or simulation) and a register `scale_hint`.
- **Where the names are used:** HTTP field names, history `fields=` and protocol maps all use them. `GET /api/points` lists them all.
- **BESS:**
  - RW: `p_setpoint_kw`, `q_setpoint_kvar`, `mode_cmd`.
  - Measurements: commanded vs actual P/Q, S, SOC, available energy and power, status, `limit_flags`, aux P, terminal voltage.
  - Nameplate ratings.
- **PV:**
  - RW: `p_limit_kw`, `p_limit_pct`, `q_setpoint_kvar`, `pf_setpoint`.
  - Measurements: available, limit, actual P/Q/S/pf, curtailment, irradiance, status, flags, voltage.
  - Nameplate ratings.
- **Load:** P, Q, S, pf, voltage.
- **POI:** P, Q, S, pf, V (kV, pu), angle, current, site losses.
- **Feeder meter:** P, Q, S, pf, MV bus V (kV, pu), HV-side current, `meter_state` (STALE on non-convergence, like the POI).
- **Site:** `step_id`, `sim_time_epoch_s`, `converged`, `state`, `overrun_count`.

**Per-asset Modbus maps** (stored with each site; the Modbus server below doesn't use them)
- **Format:** `ModbusMap` in `points/modbus_map.py`, with its JSON Schema at `GET /api/schemas/modbus-map`. Each site has a map for every asset (BESS, PV, load, POI meter, site status, feeder meters), stored in the database and editable at `/api/sites/{site}/modbus-maps/{asset}`. The shipped defaults are in `site_config/modbus_maps/<site>/`.
- **Contents:** each asset gets its own unit ID and port. Each map entry binds a point to a register type, address, data type, word order and scale (engineering value = raw × scale).
- **Default layout** (`default_map()`; `make modbus-maps` regenerates the default files):
  - Unit IDs run from 1 per site, in the order BESS, PV, loads, POI meter, site status, then feeder meters (last, so adding a meter moves no existing unit ID), all on port 502.
  - RW setpoints go in holding registers from 0, read-only points in input registers from 0, and nameplate points in input registers from 100.
  - Measured values are int32 at the point's `scale_hint`; enums and flags are uint16. Word order is big.
- **Validation:**
  - overlapping registers are rejected;
  - every entry must name a real point, with RW points on writable registers;
  - the asset must exist in that site;
  - a unit ID + port can belong to only one map in a site.

  If a site later drops an asset, its map is kept but listed as `orphaned: true`. Deleting a site deletes its maps.

## Modbus server
- **What:** one Modbus TCP aggregator (container port 502, host port `POWERFLOW_MODBUS_PORT` = 1502; unit id 1), started when the active site has `interfaces.modbus.enabled`. Settings: `MODBUS_HOST`, `MODBUS_PORT`, `MODBUS_UNIT_ID`, `POINT_STANDARD_DIR`.
- **Register layout:** from the PAE point standard in `docs/point-standard/` (shipped in the image). Each device owns 100 registers: site 0 (met station 100), BESS from 1000, PV from 2000, loads from 3000, POI meter 4000 and feeder meters from 4100. The layout is published as the contract `contracts/modbus/powerflow.registers.json` (`make contract`), and `GET /api/modbus/registers` lists the active site's. Details are in `docs/point-standard/README.md`.
- **Frequency:** not simulated; `Hz` is a random signal around 60 Hz (± 0.02, new value every sim second, seeded), from the reusable `RandomSignal` in `src/powerflow/point_standard/random_signal.py`.
- **Values:** the CSVs' `powerflow_server` column says which points are served: `yes` (a simulation value × a unit factor), `calc` (derived: per-phase values, SunSpec state and alarm codes, energy counters, fleet totals) or `no` (reads 0). All of that code is in `src/powerflow/point_standard/`.
- **Read-only:** FC03 and FC04 return the same values; writes get ILLEGAL_FUNCTION. Setpoints stay on HTTP.
- Adapter details: `src/powerflow/interfaces/modbus/README.md`.

## Tests
- **`make -C services/powerflow test`** runs the unit tests with no Docker. They use an in-memory configuration store and take about 45 s. They cover:
  - the models, profiles and config validation;
  - the network: the hand-calculated transformer, power balance, scaling and non-convergence;
  - the engine: determinism, 24 h SOC, and real-time pacing with a fake clock;
  - points, the setpoint path and every API route;
  - the default Modbus maps against their generator.
- **`make -C services/powerflow test-integration`** runs the same repository tests against a real Postgres, in a throwaway compose project (tmpfs, no host ports). It also checks idempotent migrations, and that the app seeds the defaults and keeps edits across a restart.
