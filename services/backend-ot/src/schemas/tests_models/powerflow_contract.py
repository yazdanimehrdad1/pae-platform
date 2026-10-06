"""
Strict models of powerflow's published contracts, as the dev seed reads them:
`contracts/modbus/powerflow.registers.json` (the Modbus server's register layout) and
`contracts/powerflow/sites.json` (the default sites' topology).

TEST-ONLY: used by the dev seeder (`tests/seed_db/powerflow_seed.py`). `extra="forbid"` and
the Literal pins make a contract change fail the seed loudly instead of seeding wrong data.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PowerflowDeviceKind = Literal[
    "site", "met_station", "bess", "pv", "load", "poi_meter", "feeder_meter"
]
PowerflowDataType = Literal[
    "uint16", "int16", "uint32", "int32", "uint64", "int64", "float32",
    "enum16", "enum32", "bitfield16", "bitfield32",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- contracts/modbus/powerflow.registers.json --------------------------------------------


class PowerflowRegister(_Strict):
    offset: int = Field(..., ge=0)
    point: str = Field(..., min_length=1)
    label: str
    qty: str
    tier: str
    data_type: PowerflowDataType
    width: int = Field(..., ge=1, le=4)
    signed: bool
    scale: float
    unit: str
    powerflow_server: Literal["yes", "calc", "no"]
    enum_detail: dict[str, str] | None
    bitfield_detail: dict[str, str] | None


class PowerflowDeviceType(_Strict):
    point_list: str
    registers: list[PowerflowRegister]


class PowerflowDeviceRef(_Strict):
    kind: PowerflowDeviceKind
    asset_id: str = Field(..., min_length=1)
    base: int = Field(..., ge=0)


class PowerflowGroup(_Strict):
    group: str
    base: int
    devices: str


class PowerflowRegistersContract(_Strict):
    comment: str = Field(alias="$comment")
    contract: Literal["powerflow/modbus-registers"]
    version: Literal[1]
    register_numbering: Literal["zero_based"]
    register_tables: str
    byte_order: Literal["big_endian"]
    word_order: Literal["msw_first"]
    port: int
    port_note: str
    unit_id: int
    chunk_registers: int
    address: str
    groups: list[PowerflowGroup]
    device_types: dict[PowerflowDeviceKind, PowerflowDeviceType]
    default_sites: dict[str, list[PowerflowDeviceRef]]


# -- contracts/powerflow/sites.json --------------------------------------------------------


class PowerflowTransformer(_Strict):
    s_rated_kva: float
    vn_hv_kv: float
    vn_lv_kv: float
    z_pct: float


class PowerflowGrid(_Strict):
    vn_kv: float
    sc_mva: float
    x_r: float


class PowerflowPoi(_Strict):
    has_line: bool


class PowerflowCollector(_Strict):
    id: str
    has_feeder: bool


class PowerflowBess(_Strict):
    id: str
    name: str
    collector: str
    s_rated_kva: float
    p_discharge_max_kw: float
    p_charge_max_kw: float
    v_lv_kv: float
    capacity_kwh: float
    transformer: PowerflowTransformer


class PowerflowPv(_Strict):
    id: str
    name: str
    collector: str
    dc_kwp: float
    p_max_kw: float
    s_rated_kva: float
    v_lv_kv: float
    transformer: PowerflowTransformer


class PowerflowLoad(_Strict):
    id: str
    name: str
    bus: str = Field(..., description='"poi" or a collector id')
    transformer: PowerflowTransformer | None


class PowerflowMeter(_Strict):
    id: str
    name: str
    asset: str = Field(..., description="The BESS, PV or load whose transformer it meters")


class PowerflowModbus(_Strict):
    enabled: bool
    port: int
    unit_id: int


class PowerflowSite(_Strict):
    display_name: str
    grid: PowerflowGrid
    poi: PowerflowPoi
    collectors: list[PowerflowCollector]
    bess: list[PowerflowBess]
    pv: list[PowerflowPv]
    loads: list[PowerflowLoad]
    meters: list[PowerflowMeter]
    modbus: PowerflowModbus
    devices: list[PowerflowDeviceRef]


class PowerflowSitesContract(_Strict):
    comment: str = Field(alias="$comment")
    contract: Literal["powerflow/sites"]
    version: Literal[1]
    units: str
    poi_bus: str
    devices_note: str
    sites: dict[str, PowerflowSite]
