"""Response bodies of the HTTP API (the published contract)."""

from typing import Literal

from pydantic import BaseModel, Field

from intelli_gateway.schemas.tools import JSONValue


class ToolCallResponse(BaseModel):
    name: str
    args: dict[str, JSONValue]
    summary: str = Field(description="The start of the tool result, for display and debugging.")
    duration_ms: float
    is_error: bool


class UsageResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class AskResponse(BaseModel):
    conversation_id: str
    answer: str
    stop_reason: str = Field(
        description="end_turn (normal), max_tokens, refusal, max_iterations or timeout."
    )
    iterations: int
    model: str | None
    tool_calls: list[ToolCallResponse]
    usage: UsageResponse


class SiteResponse(BaseModel):
    site_id: int
    name: str
    description: str | None
    capacity_kw: float | None
    timezone: str


class ToolSpecResponse(BaseModel):
    name: str
    description: str
    input_schema: dict[str, JSONValue]


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    ok: bool


class ReadinessResponse(BaseModel):
    ok: bool
    database: Literal["ok", "unavailable", "not_configured"] = Field(
        description=(
            "Its own Postgres: not_configured when DATABASE_URL is unset (forecasts in memory)."
        )
    )
