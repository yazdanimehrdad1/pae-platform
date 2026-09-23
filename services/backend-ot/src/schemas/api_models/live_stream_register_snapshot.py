"""Pydantic models for the live stream register snapshot debugging endpoint."""


from pydantic import BaseModel


class LiveStreamRegisterSnapshotEntry(BaseModel):
    address: int
    values: list[int | float | None]
    label: str = "unknown"
    data_type: str = "int16"


class LiveStreamRegisterSnapshotResponse(BaseModel):
    timestamps: list[str]
    registers: list[LiveStreamRegisterSnapshotEntry]
