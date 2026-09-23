"""Pydantic models for the modbus live stream raw registers feature."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from schemas.api_models.types import SUPPORTED_NUMERIC_DATA_TYPES, NumericDataType


class LiveStreamRawRegistersRegisterConfig(BaseModel):
    label: str | None = None
    data_type: NumericDataType = "int16"
    byte_order: Literal["big", "little"] | None = None
    word_order: Literal["msw_first", "lsw_first"] | None = None

    @field_validator("data_type", mode="before")
    @classmethod
    def _coerce_data_type(cls, v: object) -> str:
        # Unknown/unsupported types fall back to int16 rather than rejecting the whole
        # stream. enum/bitfield/status_word are excluded on purpose: this path decodes
        # ad-hoc registers with no detail map to translate them against.
        if v not in SUPPORTED_NUMERIC_DATA_TYPES:
            return "int16"
        return str(v)


class LiveStreamRawRegistersParams(BaseModel):
    host: str = Field(..., description="Modbus device IP/hostname")
    port: int = Field(502, ge=1, le=65535)
    server_address: int = Field(1, ge=1, le=255, description="Modbus unit/slave ID")
    kind: Literal["holding", "input"] = Field("holding")
    start_address: int = Field(..., ge=0, le=65535)
    end_address: int = Field(..., ge=0, le=65535)
    modbus_address_mode: Literal["zero_based", "one_based"] = Field(
        "zero_based",
        description="zero_based: address sent as-is; one_based: subtract 1 before sending to device",
    )
    interval: float = Field(1.0, ge=0.5, le=60.0, description="Seconds between polls")
    duration: int = Field(3600, ge=1, le=3600, description="Session length in seconds, max 1 hour")
    byte_order: Literal["big", "little"] = Field("big")
    word_order: Literal["msw_first", "lsw_first"] = Field("msw_first")
    register_configs: dict[str, LiveStreamRawRegistersRegisterConfig] | None = Field(
        None,
        description="Optional per-address config, e.g. {\"1400\": {\"label\": \"voltage\", \"data_type\": \"float32\"}}",
    )

    @model_validator(mode="after")
    def _validate_range(self) -> "LiveStreamRawRegistersParams":
        if self.end_address < self.start_address:
            raise ValueError("end_address must be >= start_address")
        if (self.end_address - self.start_address + 1) > 125:
            raise ValueError("Address range must be <= 125 registers (single Modbus frame limit)")
        return self

    def int_register_configs(self) -> dict[int, LiveStreamRawRegistersRegisterConfig]:
        if not self.register_configs:
            return {}
        return {int(k): v for k, v in self.register_configs.items()}


class LiveStreamRawRegistersRegister(BaseModel):
    value: int | float | None = None
    label: str = "unknown"
    data_type: NumericDataType = "int16"


class LiveStreamRawRegistersEvent(BaseModel):
    timestamp: datetime
    poll: int
    registers: dict[str, LiveStreamRawRegistersRegister]


class LiveStreamRawRegistersErrorEvent(BaseModel):
    error: str
    poll: int


class LiveStreamRawRegistersDoneEvent(BaseModel):
    total_polls: int
    duration_s: int


class LiveStreamRawRegistersConnectedEvent(BaseModel):
    session_id: str


# --- Session list models ---

class LiveStreamSessionInfo(BaseModel):
    session_id: str
    status: Literal["active", "stopped"]
    host: str
    port: int
    server_address: int
    kind: Literal["holding", "input"]
    start_address: int
    end_address: int
    interval: float
    duration: int
    modbus_address_mode: str


class LiveStreamSessionsResponse(BaseModel):
    sessions: list[LiveStreamSessionInfo]


# --- Simple action response models ---

class LiveStreamStopSessionResponse(BaseModel):
    stopped: str


class LiveStreamDeleteSessionResponse(BaseModel):
    deleted: str


class LiveStreamDeleteAllSessionsResponse(BaseModel):
    cancelled_active_sessions: int
    deleted_count: int
    deleted_sessions: list[str]
