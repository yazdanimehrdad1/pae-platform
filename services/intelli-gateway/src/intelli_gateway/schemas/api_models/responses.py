"""Response bodies of the HTTP API (the published contract)."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

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
    turn_id: int = Field(description="This answer's id: for feedback on it.")
    created_at: AwareDatetime = Field(description="When it was asked (UTC).")
    answer: str
    stop_reason: str = Field(
        description="end_turn (normal), max_tokens, refusal, max_iterations or timeout."
    )
    iterations: int
    model: str | None
    tool_calls: list[ToolCallResponse]
    usage: UsageResponse


class TurnResponse(BaseModel):
    """One question and its answer in a saved conversation."""

    turn_id: int
    position: int = Field(description="0 for the conversation's first question.")
    question: str
    answer: str
    stop_reason: str
    model: str | None
    tool_calls: list[ToolCallResponse] = Field(
        description="What the AI read to answer (tools and their arguments; not the values)."
    )
    usage: UsageResponse
    duration_ms: float
    created_at: AwareDatetime
    site_local_time: str = Field(
        description="The site's local time when asked (ISO 8601 with its offset)."
    )
    feedback: Literal["up", "down"] | None
    feedback_comment: str | None
    feedback_at: AwareDatetime | None


class ConversationSummaryResponse(BaseModel):
    conversation_id: str
    site_id: int
    title: str = Field(description="The first question, shortened, unless the user renamed it.")
    created_at: AwareDatetime
    updated_at: AwareDatetime
    turns: int = Field(description="How many questions it holds.")


class ConversationResponse(BaseModel):
    conversation_id: str
    site_id: int
    title: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    turns: list[TurnResponse]


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


class MeResponse(BaseModel):
    """The logged-in user."""

    id: int
    email: str
    display_name: str
    role: Literal["engineer", "admin", "monitor"]


class UserResponse(BaseModel):
    """An account, as an admin sees it (never its password)."""

    id: int
    email: str
    display_name: str
    role: Literal["engineer", "admin", "monitor"]
    disabled: bool
    created_at: AwareDatetime
    last_login_at: AwareDatetime | None
