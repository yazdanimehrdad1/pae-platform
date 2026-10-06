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
- **First start:** the database migrations create the three default sites (`0003_default_sites.sql`) and powerflow runs the default active site, `2bess_1pv`. That site is 12.47 kV with a 100 MVA / X/R 5 grid, 2 × 2.5 MW / 10 MWh BESS, 5 MWac PV (all on 12.47/0.48 kV step-ups) and a 3 MW peak load, with a feeder meter on each step-up's 12.47 kV side.
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
| The active site | Postgres `app_state` | `POST /api/sites/{name}/activate` |
| Profile scenarios | **CSV files** in `profiles/{load,pv}/` (`PROFILES_DIR`) | `/api/profiles/{load\|pv}/{scenario}` |
| JSON Schema | generated from code | `/api/schemas/site-config` |

- **Database:** powerflow owns its own Postgres, `powerflow-postgres` (host port 5436), set by `DATABASE_URL`. The SQL migrations in `src/powerflow/storage/migrations/` run at startup.
- **Writes:** every write is validated before it's stored.
- **The database is the only store for sites.** There are no site files: a fresh database gets the three default sites and the active site from the data migration `0003_default_sites.sql` (full configs, every field explicit). Sites are stored with every field, so a later change to a code default never changes a stored site. To change a default site for everyone, add a migration; to change it in one database, `PUT /api/sites/{name}`. A deleted site is gone.
- **Site categories:** every stored site is `default` or `custom` (`GET /api/sites` lists each with its category). The three default sites (`1bess_1pv`, `2bess_1pv`, `3bess_2pv`) are `default`: they can be edited but not deleted (409). Every site created through the API is `custom`; only a migration (`0004_site_categories.sql`) sets `default`.
- **`ACTIVE_SITE`** overrides the stored active site for one run only; `GET /api/sites` then reports both (`active`, `stored_active`), and neither can be deleted.
- **Profile edits:** `PUT /api/profiles/...` writes the CSV files. In the container they live on the `powerflow-profiles` volume, which Docker seeds from the image; on the host they go straight into the repo folder.
- **Resetting:** `make -C services/powerflow down-all` deletes the database and profile volumes; the next start migrates a fresh database (the default sites) and reseeds the profile volume from the image. It's destructive, so only run it on purpose.
- **Regenerating the profile CSVs:** `make -C services/powerflow profiles`.

## Site config (JSON)
One Pydantic model (`SiteConfig`) validates the migration's default sites, `PUT /api/sites/{name}`,
what's read back from the database, and `GET /api/schemas/site-config`. Unknown keys are
rejected. The sections are:
- **`simulation`:** `step_s`, `start_time` (the sim time of step 0: an ISO time, or `"now"` = the wall clock when a run starts fresh or is reset), `speed` (sim seconds per wall-clock second, up to 100), `start_step` (a fresh run starts after this step), `autostart`, `test_mode` (enables manual stepping), `seed`, `history_size`.
- **`grid`:** `vn_kv` (12.47), `vm_pu`, `sc_mva`, `x_r`. The grid is modelled as a source behind |Z| = V²/S_sc.
- **`poi.line`:** an optional POI cable. **`poi.breaker`:** `{closed}`, the POI breaker's initial position. **`collectors`:** MV buses, each with an optional feeder line, otherwise tied to the POI bus.
- **`breaker`** on every BESS, PV and load: `{closed}` (default true), the initial position of its breaker (on the HV side of its step-up; a load without a transformer: the load itself). Breakers are named by asset id, so `"poi"` can't be an asset id.
- **`bess[]`:**
  - `inverter`: `s_rated_kva`, `p_discharge_max_kw`, `p_charge_max_kw`, `v_lv_kv`, `priority` (`p`|`q`), `ramp_kw_per_s`.
  - `battery`: `capacity_kwh`, SOC min/max/initial, `efficiency` (`charge`+`discharge`, or `round_trip`, split as √η), `aux_load_kw`.
  - `transformer`: `s_rated_kva`, `vn_hv_kv`, `vn_lv_kv`, `z_pct`, `x_r`, `no_load_loss_kw`, `i0_pct`.
- **`pv[]`:** `dc_kwp`, `loss_factor`, `inverter` (`s_rated_kva`, `p_max_kw`), `availability` (`source`: `ac_kw` | `irradiance`, plus a profile `scenario` from `profiles/pv/`, `scale` and `loop`), `transformer`.
- **`loads[]`:** `bus` (`poi` or a collector id), `profile` (`scenario` from `profiles/load/`, `scale`, `loop`), optional `noise` (% std, seeded), optional `transformer`.
- **`meters[]`:** feeder meters, each `{id, name?, transformer}`. `transformer` is the BESS, PV or load (with a transformer) whose transformer is metered on its HV side, between the MV bus and the transformer. A meter has no impedance: it reads the transformer's HV-terminal P/Q/I and the MV bus voltage.
- **`interfaces`:** `http` is always on; `modbus` starts the Modbus server (enabled on `2bess_1pv`); `dnp3` isn't implemented yet, so enabling it only logs a warning.

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
- **Real time:** tick k is due at anchor + k·step_s/`speed`. If a step overruns, the missed ticks are skipped (`step_id` jumps and the skipped time is integrated as one longer step), `overrun_count` increments and a warning is logged. `PUT /api/sim/speed` changes the speed at runtime (re-anchoring); reset or reloading the site restores `simulation.speed`.
- **States:** `start`, `pause` (resuming continues sim time without a jump), `stop` (keeps state; required to save the active site), `reset` (step `start_step`, empty history, conditions and speed from the config; `"now"` is read again), and `scheduled`: `POST /api/sim/start {"at": "<ISO time>"}` waits for that wall-clock time (lost on restart; stop cancels it).
- **Clock:** the origin (sim time of step 0) is `start_time`, or for `"now"` the wall clock at reset and when a fresh run starts (not on resume), to the second. `GET /api/sim/status` reports `start_time` (resolved), `start_step`, `speed` and `scheduled_start`.
- **Test mode:** `POST /api/sim/step?count=N` exists only with `test_mode: true` and while not running. It is used for long-horizon tests.
- **Non-convergence:** the last good values are republished with `converged: false`, SOC doesn't advance, and `nonconverged_count` increments. The loop keeps running.
- **Determinism:** the same config, profiles, seed and setpoint sequence give the same snapshots.

## Injected conditions and event scenarios
Conditions are an input to every step, like setpoints, applied live or by an event scenario:
- **Breakers** (`{"type": "breaker", "breaker": "bess1" | "poi", "closed": false}`): an open asset breaker takes the asset OFFLINE (a load: de-energised); an open POI breaker de-energises the whole site (no islanding: 0 V, 0 Hz, converged, nothing integrated).
- **Asset faults** (`asset_fault`, BESS/PV, `cause`: `trip`, `over_temperature` (BESS), `ground_fault`/`dc_overvoltage` (PV)): P = Q = 0 and status FAULT, plus the cause's alarm bit; `active: false` clears it.
- **Comm loss** (`comm_loss`, `target`: `asset`, `meter`, `poi_meter`): what the device publishes freezes at its last values with the COMM_LOSS bit (meters: STALE), and its Modbus heartbeat stops; the physics keep running underneath. Each snapshot's `conditions` carries the true state.
- **Grid events:** `grid_voltage` (`vm_pu` 0.5–1.5, the source voltage) and `grid_frequency` (`hz` 55–65); `null` restores the config's value.
- **Live:** `POST /api/sim/conditions` (any run state; the next step applies it), `GET` the current ones, `POST /api/sim/conditions/clear` (back to the config's breakers, nothing injected; stops the scenario). Reset and activate also clear them.
- **Event scenarios:** stored per site in Postgres (`event_scenarios`, deleted with the site): a list of `{at, change, label}`, where `at` is `{"kind": "step", "step": N}` (before the Nth step after the scenario starts) or `{"kind": "sim_time", "sim_time": ...}` (before the first step at or after it; one already past at start is `missed`). One plays at a time (`POST /api/sim/event-scenario/start {"name"}`, `.../stop`), deterministically under `sim/step?count=N`; skipped ticks fire every event in the gap, in order. A scenario is validated against its site when saved, when listed (`valid`/`problems` after a site edit) and when started.

## HTTP API (`/api`; OpenAPI at `/docs`)
| Area | Endpoints |
|---|---|
| Simulation | `POST sim/start` (optional `{"at"}`), `sim/pause`, `sim/stop`, `sim/reset`, `sim/step?count=N` · `PUT sim/speed` · `GET sim/status` |
| Conditions | `GET`/`POST sim/conditions` · `POST sim/conditions/clear` · `POST sim/event-scenario/start`, `sim/event-scenario/stop` |
| Event scenarios | `GET sites/{site}/event-scenarios` · `GET`/`PUT`/`DELETE sites/{site}/event-scenarios/{name}` |
| Active config | `GET config` · `GET schemas/site-config` |
| Sites | `GET sites` (name + category) · `GET`/`PUT`/`DELETE sites/{name}` (DELETE: custom sites only) · `POST sites/{name}/activate` (while stopped) |
| Profiles | `GET profiles` · `GET`/`PUT`/`DELETE profiles/{load\|pv}/{scenario}` (text/csv; DELETE refused while a site uses it) |
| Schemas | `GET schemas` · `GET schemas/{name}` (`site-config`; read-only) |
| Assets | `GET assets` (includes `meters`) · `GET assets/{bess,pv,load}/{id}` · `PUT assets/{bess,pv}/{id}/setpoint` |
| Points | `GET points` · `GET points/{name}` |
| Measurements | `GET measurements/latest`, `measurements/poi` · `GET measurements/history?from=&to=&fields=&format=json\|csv` |
| Devices (point standard) | `GET devices` · `GET devices/{kind}/{asset_id}` · `GET devices/{kind}/{asset_id}/history?points=W&points=Var&from=&to=` |
| Modbus | `GET modbus/registers` (the Modbus server's register layout for the active site) |
| Service | `GET health`, `GET version` |

**Two views of the same measurements**
- **Native** (`measurements/*`, `assets/*`, `points/*`): powerflow's own names (`bess.bess1.p_kw`), kW and 0-based codes; the snapshot is the whole simulation state (buses, transformers, losses, conditions).
- **Point standard** (`devices/*`): the site as the Modbus server's devices (site, met station, BESS, PV, loads, POI and feeder meters), each point with its standard name, label, SI unit, standard enum/bit code and the code's label. Values come from the same resolvers that fill the Modbus registers (a test checks every served value encodes to the exact register words), before encoding: Modbus rounds them to the row's `scale` and saturates them to its type. `served: no` points are null. History is resolved from each stored snapshot; points derived from a setpoint (e.g. `WSet`) are null there, since setpoints aren't recorded.

**Setpoints**
- **Partial updates:** omitted fields keep their value.
- **Invalid values → 422:** for example a non-number, an unknown mode, both `p_limit_kw` and `p_limit_pct`, or |pf| < 0.8.
- **Out-of-range values** are clamped to the static limits. The response's `accepted`, `clamped` and `flags` report what was applied.
- **Dynamic limits** (SOC, ramp) show in each measurement's `limit_flags`.

**Status codes:** 404 for an unknown asset, point, site or scenario; 409 for the wrong engine state, no data yet, or a scenario already playing; 422 for a condition that doesn't apply to the site.

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
- **Load:** P, Q, S, pf, voltage, supply state, alarms.
- **POI:** P, Q, S, pf, V (kV, pu), angle, current, site losses, `hz` (grid frequency; 0 while de-energised).
- **Breakers:** `breaker_state` (0 OPEN, 1 CLOSED) on BESS, PV, load and the POI.
- **Feeder meter:** P, Q, S, pf, MV bus V (kV, pu), HV-side current, `meter_state` (STALE on non-convergence or comm loss, like the POI).
- **Energy:** `energy_discharged_kwh`/`energy_charged_kwh` (BESS), `energy_produced_kwh`/`energy_produced_today_kwh` (PV), `energy_consumed_kwh` (load), `energy_export_kwh`/`energy_import_kwh` (POI and feeder meters). The simulation integrates them every converged step over its real length (exact for `sim/step?count=N`), holds them while the power flow fails, and restarts them on reset or activate. The full set (by direction, VAh, reactive quadrants, today) is each measurement's `energy` in the snapshot; the Modbus counters come from there.
- **Site:** `step_id`, `sim_time_epoch_s`, `converged`, `state`, `overrun_count`.

## Modbus server
- **What:** one Modbus TCP aggregator (container port 502, host port `POWERFLOW_MODBUS_PORT` = 1502; unit id 1), started when the active site has `interfaces.modbus.enabled`. Settings: `MODBUS_HOST`, `MODBUS_PORT`, `MODBUS_UNIT_ID`, `POINT_STANDARD_DIR`.
- **Register layout:** from the PAE point standard in `docs/point-standard/` (shipped in the image). Each device owns 100 registers: site 0 (met station 100), BESS from 1000, PV from 2000, loads from 3000, POI meter 4000 and feeder meters from 4100. The layout is published as the contract `contracts/modbus/powerflow.registers.json` (`make contract`), and `GET /api/modbus/registers` lists the active site's. Details are in `docs/point-standard/README.md`.
- **Frequency:** the snapshot's `poi.hz`: nominal 60 Hz or an injected excursion, plus a seeded ± 0.02 Hz wander (a new value every sim second, `models/grid.py` on the reusable `RandomSignal`); 0 on a de-energised device.
- **Injected conditions:** `BrkPos` (the last row of every device, IEC 61850 Dbpos) is the device's breaker; a faulted inverter reports InvSt FAULT and counts in the site's `NInvFlt`; an open POI breaker is site `GridMode` BLACKOUT; a comm-lost device's values and `Hb` freeze and the site raises DEVICE_COMM_LOSS.
- **Values:** the CSVs' `powerflow_server` column says which points are served: `yes` (a simulation value × a unit factor), `calc` (derived: per-phase values, SunSpec state and alarm codes, energy counters, fleet totals) or `no` (reads 0). All of that code is in `src/powerflow/point_standard/`.
- **Read-only:** FC03 and FC04 return the same values; writes get ILLEGAL_FUNCTION. Setpoints stay on HTTP.
- **Lifecycle:** started or stopped whenever the engine's config changes (startup, activating a site, saving the active site). A failed start (port taken) doesn't fail the request; `GET /api/health` (`interfaces`, `interface_errors`) and `GET /api/modbus/registers` (`running`, `error`) report it.
- Adapter details: `src/powerflow/interfaces/modbus/README.md`.

## Tests
- **`make -C services/powerflow test`** runs the unit tests with no Docker. They use an in-memory configuration store holding what a migrated database holds, and take about 45 s. They cover:
  - the models, profiles and config validation;
  - the network: the hand-calculated transformer, power balance, scaling and non-convergence;
  - the engine: determinism, 24 h SOC, and real-time pacing with a fake clock;
  - points, the setpoint path and every API route;
  - the energy counters, the Modbus server over TCP and the point-standard layout, contract and resolvers.
- **`make -C services/powerflow test-integration`** runs the same repository tests against a real Postgres, in a throwaway compose project (tmpfs, no host ports). It also checks the migrations (idempotent, a fresh database gets exactly the default sites, a stale one is refreshed once by `0003`, the old default-site names are renamed by `0004`), that sites are stored with every field, and that the app keeps edits across a restart.
