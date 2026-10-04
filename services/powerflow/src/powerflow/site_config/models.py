"""The site config schema (Pydantic v2). One model backs the stored sites (PUT /sites/{name}) and
GET /schemas/site-config.

Units are in the field names (kW, kvar, kVA, kWh, kV, %, s). Sign conventions are in the README.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

# A transformer's rated voltage may differ from the bus it connects to by at most this fraction.
VOLTAGE_MATCH_TOLERANCE = 0.01
POI_BUS_ID = "poi"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SiteInfo(StrictModel):
    name: str = "Site"


class SimulationConfig(StrictModel):
    step_s: float = Field(default=1.0, gt=0, le=3600, description="Simulation step (s).")
    start_time: AwareDatetime = Field(
        default=datetime(2026, 1, 1, tzinfo=UTC),
        description="Sim clock origin (timezone-aware ISO 8601). Sim time then advances 1:1 "
        "with wall-clock.",
    )
    autostart: bool = Field(default=True, description="Start the real-time loop at startup.")
    test_mode: bool = Field(
        default=False, description="Enables POST /sim/step (manual stepping, tests only)."
    )
    seed: int = Field(default=0, ge=0, description="Seed for the load noise.")
    history_size: int = Field(
        default=3600, ge=1, le=1_000_000, description="Snapshots kept in the history buffer."
    )


class GridConfig(StrictModel):
    """The utility feeder: an ideal source behind its short-circuit impedance."""

    vn_kv: float = Field(default=12.47, gt=0, description="Nominal voltage, line-to-line (kV).")
    vm_pu: float = Field(default=1.0, ge=0.8, le=1.2, description="Source voltage (pu).")
    va_degree: float = Field(default=0.0, description="Source voltage angle (deg).")
    sc_mva: float = Field(default=100.0, gt=0, description="Short-circuit power at the POI.")
    x_r: float = Field(default=5.0, gt=0, description="Source impedance X/R ratio.")


class LineConfig(StrictModel):
    length_km: float = Field(gt=0)
    r_ohm_per_km: float = Field(ge=0)
    x_ohm_per_km: float = Field(ge=0)
    c_nf_per_km: float = Field(default=0.0, ge=0)
    max_i_ka: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def _has_impedance(self) -> Self:
        if self.r_ohm_per_km == 0 and self.x_ohm_per_km == 0:
            raise ValueError("a line needs r_ohm_per_km or x_ohm_per_km > 0")
        return self


class PoiConfig(StrictModel):
    line: LineConfig | None = Field(
        default=None, description="Optional POI line/cable between the POI and the grid."
    )


class CollectorConfig(StrictModel):
    """An MV collector bus. Without a feeder it is tied to the POI bus by a closed switch."""

    id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    feeder: LineConfig | None = None


class TransformerConfig(StrictModel):
    s_rated_kva: float = Field(gt=0)
    vn_hv_kv: float = Field(gt=0)
    vn_lv_kv: float = Field(gt=0)
    z_pct: float = Field(gt=0, le=30, description="Short-circuit impedance (%Z).")
    x_r: float = Field(default=7.0, gt=0)
    no_load_loss_kw: float = Field(default=0.0, ge=0)
    i0_pct: float = Field(default=0.0, ge=0, description="No-load current (%).")


class Priority(StrEnum):
    """Which of P and Q is kept when a setpoint exceeds the apparent power rating."""

    P = "p"
    Q = "q"


class BessInverterConfig(StrictModel):
    s_rated_kva: float = Field(gt=0)
    p_discharge_max_kw: float = Field(gt=0)
    p_charge_max_kw: float = Field(gt=0)
    v_lv_kv: float = Field(default=0.69, gt=0)
    priority: Priority = Priority.P
    ramp_kw_per_s: float | None = Field(default=None, gt=0, description="null = unlimited.")

    @model_validator(mode="after")
    def _s_covers_p(self) -> Self:
        if self.s_rated_kva < max(self.p_discharge_max_kw, self.p_charge_max_kw):
            raise ValueError("inverter s_rated_kva must be >= its max charge/discharge P")
        return self


class EfficiencyConfig(StrictModel):
    """Either charge + discharge efficiencies, or a round-trip efficiency split evenly."""

    charge: float | None = Field(default=None, gt=0, le=1)
    discharge: float | None = Field(default=None, gt=0, le=1)
    round_trip: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def _one_form(self) -> Self:
        one_way = self.charge is not None or self.discharge is not None
        if self.round_trip is not None and one_way:
            raise ValueError("give either round_trip or charge + discharge, not both")
        if self.round_trip is None and (self.charge is None or self.discharge is None):
            raise ValueError("give both charge and discharge, or round_trip")
        return self

    @property
    def eta_charge(self) -> float:
        if self.round_trip is not None:
            return self.round_trip**0.5
        assert self.charge is not None
        return self.charge

    @property
    def eta_discharge(self) -> float:
        if self.round_trip is not None:
            return self.round_trip**0.5
        assert self.discharge is not None
        return self.discharge


class BatteryConfig(StrictModel):
    capacity_kwh: float = Field(gt=0)
    soc_min_pct: float = Field(default=5.0, ge=0, le=100)
    soc_max_pct: float = Field(default=95.0, ge=0, le=100)
    soc_initial_pct: float = Field(default=50.0, ge=0, le=100)
    efficiency: EfficiencyConfig = Field(
        default_factory=lambda: EfficiencyConfig(charge=0.95, discharge=0.95)
    )
    aux_load_kw: float = Field(
        default=0.0, ge=0, description="Auxiliary load, drawn from the LV bus (not the cells)."
    )

    @model_validator(mode="after")
    def _soc_order(self) -> Self:
        if not self.soc_min_pct < self.soc_max_pct:
            raise ValueError("soc_min_pct must be < soc_max_pct")
        if not self.soc_min_pct <= self.soc_initial_pct <= self.soc_max_pct:
            raise ValueError("soc_initial_pct must be within [soc_min_pct, soc_max_pct]")
        return self


AssetId = str


class BessConfig(StrictModel):
    id: AssetId = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = None
    collector: str = "mv1"
    inverter: BessInverterConfig
    battery: BatteryConfig
    transformer: TransformerConfig


class PvAvailabilitySource(StrEnum):
    AC_KW = "ac_kw"  # the profile is available AC power (kW), column p_kw
    IRRADIANCE = "irradiance"  # the profile is irradiance (W/m2), column ghi_wm2


# Scenario names are file stems under profiles/<load|pv>/; the pattern also keeps
# them from escaping that folder.
SCENARIO_PATTERN = r"^[a-z0-9_]+$"


class ProfileRef(StrictModel):
    scenario: str = Field(
        pattern=SCENARIO_PATTERN,
        description="Profile scenario: a CSV in profiles/<load|pv>/<scenario>.csv.",
    )
    scale: float = Field(default=1.0, ge=0, description="Multiplies every profile value.")
    loop: bool = Field(default=True, description="Repeat the profile; else hold the ends.")


class PvAvailabilityConfig(ProfileRef):
    source: PvAvailabilitySource = PvAvailabilitySource.AC_KW


class PvInverterConfig(StrictModel):
    s_rated_kva: float = Field(gt=0)
    p_max_kw: float = Field(gt=0)
    v_lv_kv: float = Field(default=0.69, gt=0)
    priority: Priority = Priority.P

    @model_validator(mode="after")
    def _s_covers_p(self) -> Self:
        if self.s_rated_kva < self.p_max_kw:
            raise ValueError("inverter s_rated_kva must be >= p_max_kw")
        return self


class PvConfig(StrictModel):
    id: AssetId = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = None
    collector: str = "mv1"
    dc_kwp: float = Field(gt=0)
    loss_factor: float = Field(default=0.0, ge=0, lt=1, description="Fraction lost before AC.")
    inverter: PvInverterConfig
    availability: PvAvailabilityConfig
    transformer: TransformerConfig


class NoiseConfig(StrictModel):
    p_std_pct: float = Field(default=0.0, ge=0, le=50)
    q_std_pct: float = Field(default=0.0, ge=0, le=50)


class LoadConfig(StrictModel):
    id: AssetId = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = None
    bus: str = Field(default=POI_BUS_ID, description='"poi" or a collector id.')
    profile: ProfileRef
    noise: NoiseConfig | None = None
    transformer: TransformerConfig | None = Field(
        default=None, description="Optional transformer; its LV side feeds the load."
    )


class MeterConfig(StrictModel):
    """A feeder meter on the HV side of an asset's transformer (between the MV bus and the
    transformer), so it reads P/Q after the transformer losses. Positive = toward the MV bus."""

    id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = None
    transformer: AssetId = Field(
        description="The BESS, PV or load (with a transformer) whose transformer is metered."
    )


class InterfaceToggle(StrictModel):
    enabled: bool = False


class HttpInterfaceConfig(StrictModel):
    # HTTP is the control plane (start/stop, config), so it can't be turned off.
    enabled: Literal[True] = True


class ModbusInterfaceConfig(StrictModel):
    """The Modbus TCP server: one read-only aggregator laid out by the PAE point standard (see
    GET /api/modbus/registers). Started or stopped when the site is activated or saved."""

    enabled: bool = False


class InterfacesConfig(StrictModel):
    http: HttpInterfaceConfig = Field(default_factory=HttpInterfaceConfig)
    modbus: ModbusInterfaceConfig = Field(default_factory=ModbusInterfaceConfig)
    dnp3: InterfaceToggle = Field(default_factory=InterfaceToggle)


def _default_collectors() -> list[CollectorConfig]:
    return [CollectorConfig(id="mv1")]


def _close(value: float, reference: float) -> bool:
    return abs(value - reference) <= VOLTAGE_MATCH_TOLERANCE * reference


class SiteConfig(StrictModel):
    """A grid-connected site: the utility feeder, the POI, MV collectors and N BESS/PV/loads."""

    schema_version: Literal[1] = 1
    site: SiteInfo = Field(default_factory=SiteInfo)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    grid: GridConfig = Field(default_factory=GridConfig)
    poi: PoiConfig = Field(default_factory=PoiConfig)
    collectors: list[CollectorConfig] = Field(default_factory=_default_collectors, min_length=1)
    bess: list[BessConfig] = Field(default_factory=list)
    pv: list[PvConfig] = Field(default_factory=list)
    loads: list[LoadConfig] = Field(default_factory=list)
    meters: list[MeterConfig] = Field(default_factory=list)
    interfaces: InterfacesConfig = Field(default_factory=InterfacesConfig)

    @model_validator(mode="after")
    def _references(self) -> Self:
        collector_ids = [collector.id for collector in self.collectors]
        if len(set(collector_ids)) != len(collector_ids):
            raise ValueError("collector ids must be unique")
        if POI_BUS_ID in collector_ids:
            raise ValueError(f'"{POI_BUS_ID}" is reserved and can\'t be a collector id')

        asset_ids = [asset.id for asset in [*self.bess, *self.pv, *self.loads]]
        duplicates = sorted({asset_id for asset_id in asset_ids if asset_ids.count(asset_id) > 1})
        if duplicates:
            raise ValueError(f"asset ids must be unique across bess/pv/loads: {duplicates}")

        for asset in [*self.bess, *self.pv]:
            if asset.collector not in collector_ids:
                raise ValueError(f"{asset.id}: unknown collector {asset.collector!r}")
            self._check_step_up(asset.id, asset.transformer, asset.inverter.v_lv_kv)
        for load in self.loads:
            if load.bus != POI_BUS_ID and load.bus not in collector_ids:
                raise ValueError(f"{load.id}: unknown bus {load.bus!r}")
            if load.transformer is not None:
                self._check_hv(load.id, load.transformer)
        self._check_meters()
        return self

    def _check_meters(self) -> None:
        meter_ids = [meter.id for meter in self.meters]
        if len(set(meter_ids)) != len(meter_ids):
            raise ValueError("meter ids must be unique")
        transformer_owners = {asset.id for asset in [*self.bess, *self.pv]} | {
            load.id for load in self.loads if load.transformer is not None
        }
        metered: set[str] = set()
        for meter in self.meters:
            if meter.transformer not in transformer_owners:
                raise ValueError(
                    f"meter {meter.id}: {meter.transformer!r} is not a BESS, PV or load with a "
                    "transformer"
                )
            if meter.transformer in metered:
                raise ValueError(f"meter {meter.id}: {meter.transformer!r} already has a meter")
            metered.add(meter.transformer)

    def _check_hv(self, asset_id: str, transformer: TransformerConfig) -> None:
        if not _close(transformer.vn_hv_kv, self.grid.vn_kv):
            raise ValueError(
                f"{asset_id}: transformer vn_hv_kv {transformer.vn_hv_kv} doesn't match the "
                f"grid's {self.grid.vn_kv} kV"
            )

    def _check_step_up(
        self, asset_id: str, transformer: TransformerConfig, inverter_kv: float
    ) -> None:
        self._check_hv(asset_id, transformer)
        if not _close(transformer.vn_lv_kv, inverter_kv):
            raise ValueError(
                f"{asset_id}: transformer vn_lv_kv {transformer.vn_lv_kv} doesn't match the "
                f"inverter's v_lv_kv {inverter_kv}"
            )
