"""The measurement snapshot published after every step. Field names are point names (see
`powerflow.points`), so HTTP, history and future protocol maps all use the same names."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class BusMeasurement(FrozenModel):
    name: str
    vn_kv: float
    v_kv: float = Field(description="Line-to-line voltage (kV).")
    v_pu: float
    angle_deg: float


class TransformerMeasurement(FrozenModel):
    """Positive P/Q = flowing toward the grid (LV → HV)."""

    name: str
    p_hv_kw: float = Field(description="P leaving at the HV terminal.")
    q_hv_kvar: float
    p_lv_kw: float = Field(description="P entering at the LV terminal.")
    q_lv_kvar: float
    p_loss_kw: float
    q_loss_kvar: float
    loading_pct: float


class PoiMeasurement(FrozenModel):
    """The POI meter. Positive P/Q = export to the utility."""

    p_kw: float
    q_kvar: float
    s_kva: float
    pf: float = Field(description="|P|/S signed with Q (positive = exporting vars).")
    v_kv: float
    v_pu: float
    angle_deg: float
    i_a: float
    p_loss_total_kw: float = Field(description="Site losses: transformers + collector feeders.")
    q_loss_total_kvar: float
    meter_state: int
    meter_state_name: str
    alarm_flags: int
    alarm_flag_names: list[str]


class MeterMeasurement(FrozenModel):
    """A feeder meter on the HV side of an asset's transformer. Positive P/Q = toward the MV
    bus (after the transformer losses)."""

    id: str
    transformer: str = Field(description="The asset whose transformer is metered.")
    p_kw: float
    q_kvar: float
    s_kva: float
    pf: float = Field(description="|P|/S signed with Q (positive = vars toward the MV bus).")
    v_kv: float = Field(description="MV bus voltage, line-to-line.")
    v_pu: float
    i_a: float = Field(description="Current on the transformer's HV side.")
    meter_state: int
    meter_state_name: str


class BessMeasurement(FrozenModel):
    """Generator convention: P > 0 discharging."""

    id: str
    p_cmd_kw: float
    q_cmd_kvar: float
    p_kw: float
    q_kvar: float
    s_kva: float
    soc_pct: float
    energy_available_discharge_kwh: float
    energy_available_charge_kwh: float
    p_available_discharge_kw: float
    p_available_charge_kw: float
    status: int
    status_name: str
    limit_flags: int
    limit_flag_names: list[str]
    aux_p_kw: float
    v_lv_pu: float
    v_lv_kv: float
    operating_state: int
    operating_state_name: str
    alarm_flags: int
    alarm_flag_names: list[str]


class PvMeasurement(FrozenModel):
    id: str
    p_available_kw: float
    p_limit_active_kw: float
    p_kw: float
    q_kvar: float
    s_kva: float
    pf: float
    curtailment_kw: float
    irradiance_wm2: float
    status: int
    status_name: str
    limit_flags: int
    limit_flag_names: list[str]
    v_lv_pu: float
    v_lv_kv: float
    inverter_state: int
    inverter_state_name: str
    alarm_flags: int
    alarm_flag_names: list[str]


class LoadMeasurement(FrozenModel):
    """Load convention: P > 0 consuming."""

    id: str
    p_kw: float
    q_kvar: float
    s_kva: float
    pf: float
    v_pu: float
    supply_state: int
    supply_state_name: str
    alarm_flags: int
    alarm_flag_names: list[str]


class Snapshot(FrozenModel):
    step_id: int = Field(description="Sim tick number; increases by 1 per step (gaps = skipped).")
    sim_time: datetime
    converged: bool = Field(
        description="False: the power flow failed this step and the values are the last good ones."
    )
    poi: PoiMeasurement
    buses: list[BusMeasurement]
    transformers: list[TransformerMeasurement]
    bess: list[BessMeasurement]
    pv: list[PvMeasurement]
    loads: list[LoadMeasurement]
    meters: list[MeterMeasurement] = Field(description="Feeder meters, in config order.")
