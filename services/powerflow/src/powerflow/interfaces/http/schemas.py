"""HTTP response models that aren't core models already."""

from datetime import datetime

from pydantic import BaseModel, Field

from powerflow.core.engine import RunState
from powerflow.core.setpoints import BessSetpointState, PvSetpointState
from powerflow.core.snapshot import (
    BessMeasurement,
    LoadMeasurement,
    PoiMeasurement,
    PvMeasurement,
)
from powerflow.point_standard import DeviceKind, ServerSupport
from powerflow.points import PointDef
from powerflow.site_config import BessConfig, LoadConfig, MeterConfig, PvConfig

# The shape FastAPI's `responses=` takes (extra OpenAPI responses per status code).
OpenApiResponses = dict[int | str, dict[str, object]]


class HealthResponse(BaseModel):
    ok: bool
    state: RunState
    interfaces: list[str] = Field(description="Protocol interfaces running now (http, modbus).")
    interface_errors: dict[str, str] = Field(
        description="Interfaces the active site enables that failed to start, with the reason."
    )


class VersionResponse(BaseModel):
    service: str
    api_version: str
    pandapower_version: str
    python_version: str


class ErrorResponse(BaseModel):
    detail: str


class AssetsResponse(BaseModel):
    """Every asset with its static parameters (as configured)."""

    bess: list[BessConfig]
    pv: list[PvConfig]
    loads: list[LoadConfig]
    meters: list[MeterConfig]


class BessAssetResponse(BaseModel):
    config: BessConfig
    setpoint: BessSetpointState
    measurement: BessMeasurement | None = Field(description="null before the first step.")


class PvAssetResponse(BaseModel):
    config: PvConfig
    setpoint: PvSetpointState
    measurement: PvMeasurement | None


class LoadAssetResponse(BaseModel):
    config: LoadConfig
    measurement: LoadMeasurement | None


class PoiResponse(BaseModel):
    step_id: int
    sim_time: datetime
    converged: bool
    poi: PoiMeasurement


class PointsResponse(BaseModel):
    naming: str = "<asset_type>.<asset_id>.<point>"
    point_lists: dict[str, list[PointDef]]
    names: list[str] = Field(description="Every point name for the current site config.")


class PointValueResponse(BaseModel):
    name: str
    value: float | int
    unit: str


HistoryValue = float | int | str


class HistoryResponse(BaseModel):
    count: int
    fields: list[str]
    rows: list[dict[str, HistoryValue]] = Field(
        description="One row per snapshot: sim_time, step_id and the requested fields."
    )


class ModbusRegister(BaseModel):
    address: int = Field(description="Zero-based register address (holding and input alike).")
    point: str = Field(description="Point name from the PAE point standard.")
    data_type: str
    scale: float = Field(description="Engineering value = raw × scale.")
    unit: str
    powerflow_server: ServerSupport


class ModbusDevice(BaseModel):
    kind: DeviceKind
    asset_id: str
    base: int
    registers: list[ModbusRegister]


class ModbusRegistersResponse(BaseModel):
    """The Modbus server's register layout for the active site."""

    enabled: bool = Field(description="Whether the active site enables interfaces.modbus.")
    running: bool = Field(description="Whether the Modbus server is actually serving now.")
    error: str | None = Field(description="Why it failed to start, if it did.")
    port: int = Field(description="The port the server listens on (inside the container).")
    unit_id: int
    devices: list[ModbusDevice]
