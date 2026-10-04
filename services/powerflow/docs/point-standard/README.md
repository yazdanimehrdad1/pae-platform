# PAE standard point list

This is the reference list of Modbus points for each kind of power asset on a PAE site. A device map, a simulator or the EMS should name, scale and interpret a point the way this list says. Vendor register maps stay as they are; what this standard fixes is the meaning each register is mapped to.

**Status:** draft v0.1 (2026-10-02). powerflow's Modbus server serves it (see [powerflow Modbus server](#powerflow-modbus-server)); the other services don't conform yet. See [Alignment gaps](#alignment-gaps) for what each would change.

This folder lives in powerflow (`services/powerflow/docs/point-standard/`) because powerflow reads it at runtime: its Modbus server takes the register layout and point list from these CSVs, and its image ships them. It is hand-written; consumers use the generated contract `contracts/modbus/powerflow.registers.json` (`make -C services/powerflow contract`), or `GET /api/modbus/registers` for the running site.

## Files

| File | Asset | Based on |
|---|---|---|
| [common.csv](common.csv) | identity block every device carries, plus the nameplate block every DER carries | SunSpec 1, 702 |
| [bess.csv](bess.csv) | energy storage: the PCS AC side and the battery/BMS | SunSpec 701, 704, 802, 803 |
| [pv_inverter.csv](pv_inverter.csv) | PV inverter, AC side and DC side | SunSpec 701, 704, 714 |
| [meter.csv](meter.csv) | revenue meter or POI meter (3-phase) | SunSpec 203 |
| [relay_breaker.csv](relay_breaker.csv) | protection relay with its breaker | IEC 61850 XCBR, PTRC, RREC, RSYN |
| [transformer.csv](transformer.csv) | power transformer, OLTC, monitoring | IEC 61850 YPTR, YLTC, STMP, SIML |
| [genset.csv](genset.csv) | diesel/gas genset controller | SunSpec 701/704, IEC 61850-7-420, J1939 |
| [met_station.csv](met_station.csv) | irradiance and weather | SunSpec 302, 307, 308 |
| [plant_controller.csv](plant_controller.csv) | PPC/site controller: POI view, fleet totals, site setpoints | PAE |
| [load.csv](load.csv) | metered load, or a controllable one | SunSpec 203 + PAE |
| [enums.csv](enums.csv) | every enum and bitfield referenced above | SunSpec, IEC 61850, PAE |

**How the files combine.** A device gets several lists, not one:
- **Every device** carries the identity rows of `common.csv`: `Mn`, `Md`, `SN`, `Vr`.
- **A DER** (BESS, PV inverter, genset) also carries the nameplate rows: `WMaxRtg`, `VAMaxRtg`, and the rest.
- **A relay that also meters** implements `relay_breaker.csv` plus `meter.csv`.
- **A transformer with its own metering** adds `meter.csv`.
- **A multifunction device** implements each list that applies to it. For example, a hybrid inverter implements `pv_inverter.csv` plus the battery rows of `bess.csv`.

## Columns

| Column | Meaning |
|---|---|
| `point` | Standard name, unique within its file. `_<n>` marks a repeated point, numbered from 1: `POAI_1`, `POAI_2`, `DCA_3`. |
| `label` | Readable name for the UI. |
| `qty` | A key for the physical quantity that is the same across all assets. A meter's `PhVphAB` and an inverter's `VL1L2` are both `v_ab`, so code can look a quantity up with `qty` whatever the asset type. |
| `tier` | **M** = mandatory: the EMS, historian or UI depends on it. **R** = recommended. **O** = optional. |
| `kind` | `measurement`, `status`, `alarm`, `counter` (accumulates, never decreases), `setpoint` (written by the EMS), `nameplate` (static). |
| `access` | `R` read-only, `RW` read/write, `W` write-only command. |
| `unit` | Engineering unit after scaling. |
| `data_type`, `scale` | Recommended register encoding. Engineering value = raw × scale. |
| `sign` | Sign convention; see [Sign conventions](#sign-conventions). |
| `enum_ref` | The key into `enums.csv`, where each code or bit has a description. |
| `enum_detail` | Required on every enum point; empty otherwise. JSON map of **value → label**, e.g. `{"1":"OFF","2":"EMPTY","3":"DISCHARGING","4":"CHARGING",…}`. This is the format backend-ot stores in `device_points.enum_detail`, so it can be copied in as-is. |
| `bitfield_detail` | Required on every bitfield point; empty otherwise. JSON map of **bit number → label** (bit 0 = least significant bit), e.g. `{"0":"GROUND_FAULT","1":"DC_OVER_VOLT",…}`. This is the format backend-ot stores in `device_points.bitfield_detail`; it adds the `bit-` prefix itself. |
| `source`, `source_ref` | Where the definition comes from (`SunSpec 802 SoC`, `IEC 61850 XCBR.Pos`, `PAE`). |
| `powerflow_server` | Whether powerflow's Modbus server fills the point: **`yes`** = straight from a simulation result (times a unit factor), **`calc`** = derived from results (per-phase values on the balanced network, state and alarm translations, energy counters, fleet sums; the code is in `services/powerflow/src/powerflow/point_standard/`), **`no`** = not simulated, the register reads 0. |
| `mock_modbus`, `powerflow` | What today's register or point is called in each service, so they can be aligned later. `(kW)` means the existing point uses a different unit. `(different codes)` means it is the same idea with a different numbering. `(partial)` means it covers only part of the point. |

## Conventions

### Names
- **SunSpec names are used exactly as SunSpec spells them.** The name comes from the SunSpec model that owns the point:
  - meters use model 203: `PhVphAB`, `AphA`, `W`, `VAR`, `VA`, `TotWhExp`;
  - DERs use model 701: `VL1L2`, `AL1`, `Var`, `TotWhInj`, `InvSt`;
  - batteries use model 802: `SoC`, `SoH`, `ChaSt`, `State`.

  Because each name comes from its own model, the same quantity can be spelled two ways. Reactive power is `VAR` on a meter (203) and `Var` on a DER (701). Use `qty` to match them up.
- **Two deliberate renames.** In `bess.csv`, 802's DC-side `V`, `A` and `W` become `DCV`, `DCA` and `DCW`. The AC-side `W` from 701 is already in that file, and a name may appear only once per file. `DCV/DCA/DCW` are also SunSpec's own names in model 714.
- **Where SunSpec has no model,** points are named in the same CamelCase style:
  - relay, breaker and transformer names come from the IEC 61850 data object, e.g. `Pos`, `TapPos`, `OilTmp`;
  - genset, plant-controller and other extension names start with `source=PAE`.

### Units and scaling
- **Units are SI with no prefixes:** W, var, VA, V, A, Hz, Wh, varh, VAh, degC and %. kW and MW never appear in a point definition.

  A device that reports kW keeps its registers as they are; its map converts with scale 1000. This removes today's mix of W, kW and MW for the same quantity.
- **PF is a ratio from −1 to 1.** SunSpec 203 lists PF in Pct, but this standard does not use percent for PF.
- **SunSpec `_SF` scale-factor registers are not points.** The `data_type` and `scale` columns give a recommended fixed encoding instead.

  A SunSpec device keeps its own `_SF` registers. Its device map reads `_SF` and applies it, and only the engineering value is stored.

### Sign conventions

| `sign` | Rule | Applies to |
|---|---|---|
| `gen` | Generator convention: **+ = injecting / exporting** | BESS (**+ = discharging, − = charging**), PV, genset; BESS DC current and power (+ = out of the battery) |
| `load` | Load convention: **+ = consuming** | loads, BESS auxiliary power |
| `ref` | **+ = power flowing in the meter's reference direction** | meters. **A POI meter's reference direction is export (site → grid).** The PPC `SiteW`/`WSet` follow the same direction. |
| `pf` | **The sign of PF is the sign of var** in the same convention (+ = over-excited, i.e. injecting var, for `gen`/`ref`; + = lagging for `load`) | every `PF` row |

Many revenue meters, and SunSpec meter devices, report **+ = import** (delivered to the customer). When a meter does that, its map applies scale −1 to `W`, `WphX`, `VAR` and `VARphX`. It also swaps which lifetime counter feeds `TotWhImp` and which feeds `TotWhExp`. Check this against the meter manual during commissioning. The BESS and POI conventions match powerflow's.

### Enums
- **SunSpec enums keep SunSpec's numbers**, for example 802 `ChaSt` 3 = DISCHARGING and 4 = CHARGING, and 701 `InvSt` 3 = RUNNING. Do not renumber them. A map translates vendor codes to these numbers.
- **PAE enums** (`pae.*`) are 0-based, except where they reuse IEC 61850 `Dbpos` (0 intermediate, 1 open, 2 closed, 3 bad state).
- **Bitfields:** bit 0 is the least significant bit, and a set bit means the condition is active.
- **Commands** (`pae.Cmd`): write 1 to execute. The device resets the register to 0.

### Register encoding (recommended)
- **Byte and word order:** big-endian, high word first. This is the Modbus/SunSpec norm.
- **Register tables:** input registers (FC04) for `R` points, holding registers (FC03/06/16) for `RW`/`W` points. Many devices put everything in holding registers, which is fine.
- **Every point is 16-bit (one register) except:**
  - lifetime energy counters, which would roll over within days at 16 bits;
  - alarm words that use bits above 15 (SunSpec `701.Alrm` and `802.Evt1`, `203.Evt`, `pae.TrpCause`, `pae.GenAlrm`);
  - the `FltTms` timestamp.

  Every other alarm word is bitfield16.
- **Default 16-bit scales,** sized for the reference sites (assets up to 5.5 MVA and 10 MWh, a 690 V LV bus, a 12.47 kV collector):

  | Quantity | Type | Scale | Resolution | Range |
  |---|---|---|---|---|
  | W, var, VA (power, setpoints, ratings) | int16 / uint16 | 1000 | 1 kW | ±32.7 MW / 65.5 MW |
  | Wh (ratings, available energy, daily energy) | uint16 | 1000 | 1 kWh | 65.5 MWh |
  | Wh, varh, VAh lifetime counters | uint32 | 1000 | 1 kWh | 4.29 TWh |
  | V at DER terminals / LV (`LLV`, `VL1L2`, `DCV`, `BattV`) | uint16 | 0.1 | 0.1 V | 6553 V |
  | V at MV (meter, plant controller, load, transformer) | uint16 | 1 | 1 V | 65.5 kV |
  | AC and total DC current | int16 / uint16 | 1 | 1 A | ±32.7 kA |
  | Per-MPPT/string DC current (`DCA_<n>`) | int16 | 0.1 | 0.1 A | ±3276 A |
  | Hz | uint16 | 0.01 | 0.01 Hz | 655 Hz |
  | PF | int16 | 0.001 | 0.001 | ±1 |
  | %, temperatures | uint16 / int16 | 0.1 | 0.1 | |

  These are defaults for a site of this size. Pick a different scale when a device doesn't fit:
  - a small device such as mock `device_1` (3 kW) would read only 0 to 3 at scale 1000, so use scale 1 or 10;
  - HV (> 65 kV) would overflow at scale 1, so use scale 10.
- **enum16** for every enum.
- **Addresses and unit ids are not standardized.** They belong to each vendor's map.

### Controls and fail-safe
- **Enables:** controllable devices put each setpoint behind an enable (`WSetEna`, `VarSetEna`, `WMaxLimPctEna`), as SunSpec 704 does. Writing the setpoint alone does not activate it.
- **Heartbeat:** the controller writes `CtrlHb` every cycle. A device that sees `CtrlHb` stop changing reverts to safe values. SunSpec 704 defines `*Rvrt` reversion setpoints for this; add them if a site needs them.
- **Local/remote:** `LocRemCtl` must be REMOTE before a device accepts remote commands.

## Mandatory points at a glance

| Asset | Tier-M points |
|---|---|
| Every DER | `WMaxRtg`, `VAMaxRtg` |
| BESS | `W` `Var` `VA` `PF` `Hz` `LLV` `InvSt` `ConnSt` `Alrm` · `SoC` `ChaSt` `State` `Evt1` · `WHRtg` `WChaRteMax` `WDisChaRteMax` · `WSetEna` `WSet` |
| PV inverter | `W` `Var` `VA` `PF` `Hz` `LLV` `TotWhInj` `DCW` `InvSt` `ConnSt` `Alrm` · `WMaxLimPctEna` `WMaxLimPct` |
| Meter | `PhVphAB` `PhVphBC` `PhVphCA` `PPV` · `AphA` `AphB` `AphC` · `W` `VAR` `VA` `PF` `Hz` · `TotWhImp` `TotWhExp` |
| Relay/breaker | `Pos` `TrpSt` `TrpCause` `RlyHealthy` · `CmdOpen` `CmdClose` |
| Transformer | `OilTmp` `WdgTmpHot` `Alrm` |
| Genset | `W` `Var` `VA` `PF` `Hz` `LLV` · `GenSt` `CtrlMode` `GenBrkPos` `AlrmShtdn` `FuelLvl` · `CmdStart` `CmdStop` |
| Met station | `GHI` `POAI_<n>` `TmpAmb` |
| Plant controller | `SiteW` `SiteVar` `SitePF` `SiteHz` `SiteV` · `PMode` `QMode` `WSet` `VarSet` `Alrm` |
| Load | `W` `VAR` `VA` `PF` |

## Alignment gaps

The `mock_modbus` and `powerflow` columns in the CSVs map each point row by row. The table below summarizes what each service would change to conform. It is only a summary: each service is changed in its own task, provider first, with its contract regenerated.

| Service | Gap |
|---|---|
| mock-modbus | Has no meter, relay, genset, transformer or met-station device; the only meter-like points are the POI block inside `device_3`. BESS power and current are unsigned, so direction is lost. Units are mixed (W/kW, Wh/kWh/MWh). The two meters disagree on frequency (50 Hz vs 60 Hz). Enums are 1-based custom codes. The contract has no access, data_type or word-order field. |
| powerflow | Its Modbus server serves this standard (the `powerflow_server` column): per-phase values on the balanced network, SunSpec state and alarm codes, energy counters (integrated by the simulation every step), fleet totals, and `Hz` as a random signal around 60 Hz (frequency isn't modelled). Its own HTTP point list (`contracts/powerflow/points.json`) keeps powerflow's names, kW units and 0-based enums; the `powerflow` column maps them. |
| backend-ot | The `STANDARDIZED` points (`device_standardized_points.py`) are three placeholders per type that nothing polls. They could be replaced by the tier-M rows of these files, with `qty` as the lookup key. Code finds points by native name (`active_power`, `poi_active_power_total`, `inverter_state`, `battery_state`, `bms_state`), and SLD roles (`vab`, `ia`, `soc`, `power`) need a mapping to `qty`. Device types have no METER template, and no type for TRANSFORMER or MET. |

## powerflow Modbus server

powerflow serves the simulated site as one Modbus TCP aggregator: one port (502 in the container, 1502 on the dev host), one unit id (1), when the active site sets `interfaces.modbus.enabled`.

| Group | Base address | Devices (100 registers each) |
|---|---|---|
| Site | 0 | plant controller (`plant_controller.csv`) at 0; met station (`met_station.csv`) at 100 when a PV is irradiance-driven |
| BESS | 1000 | BESS n at 1000 + 100·(n−1) |
| PV | 2000 | PV n at 2000 + 100·(n−1) |
| Gensets / loads | 3000 | load n at 3000 + 100·(n−1) (no gensets in powerflow) |
| Meters / relays | 4000 | POI meter at 4000, feeder meters from 4100 in config order |

- **Inside a chunk:** the device's CSV rows in file order, then `common.csv`'s rows. Every row gets an address whether served or not, so serving more points later moves nothing. String rows (identity text) are left out; `_<n>` rows are instance 1.
- **Addresses** are zero-based wire addresses, and holding (FC03) and input (FC04) registers return the same values.
- **Encoding:** the `data_type` and `scale` columns, big-endian, high word first; values saturate at the type's range. Points marked `no` read 0.
- **Read-only:** writes get exception 1 (illegal function). Setpoints stay on powerflow's HTTP API.
- **Frequency:** powerflow solves a steady state, so it has no frequency of its own. `Hz` / `SiteHz` come from a time-bucketed random signal (`point_standard/random_signal.py`): 60 Hz ± 0.02, a new value every sim second, the same on every device, reproducible for a given site `seed`. The same `RandomSignal` (nominal, spread, period in seconds, key) is meant for other unsimulated points later.
- **Contract:** `contracts/modbus/powerflow.registers.json` is generated from these CSVs: a register template per device kind (offsets from the device base) plus each default site's device bases. A moved offset is breaking, so add new rows at the end of a file.
- **Discovering the layout:** `GET /api/modbus/registers` lists every device, address, point, type, scale and `powerflow_server` value for the active site.

## Sources

- SunSpec Alliance information models, machine-readable JSON: <https://github.com/sunspec/models> (models 1, 203, 302, 307, 701, 702, 704, 802, 803)
- SunSpec DER Information Model Specification v1.2: <https://sunspec.org/wp-content/uploads/2025/01/SunSpec-DER-Information-Model-Specification-V1-2-1.pdf>
- SunSpec Energy Storage Models: <https://sunspec.org/wp-content/uploads/2019/08/SunSpec-Alliance-Specification-Energy-Storage-ModelsD4rev0.pdf>
- IEC 61850-7-4 MMXU reference (Schneider ION): <https://product-help.se.com/docs/ION-Reference/content/ion%20reference/iec-61850-mmxu-module.htm>
- SEL-751 feeder protection relay data sheet (Modbus map, protection elements): <https://selinc.com/api/download/10734/>
- Cummins PowerCommand Modbus register mapping: <https://csdieselgenerators.com/Images/Generators/2852/Cummins-PowerCommand-1.1-1.2-2.2-2.3-3.3-modbus-register-mapping.pdf>
- Deep Sea Electronics GenComm integration note: <http://cdn.senquip.com/wp-content/uploads/2024/04/18104724/APN0029-Rev-1.0-Modbus-Integration-With-Deep-Sea-Engine-Controller.pdf>
- IEEE C37.2 device function numbers (50/51/27/59/81/86/79/25/52)
