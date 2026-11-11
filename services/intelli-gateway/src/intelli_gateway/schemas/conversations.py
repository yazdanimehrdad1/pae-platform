"""Saved AI conversations: one record per question and answer (a turn), and the summary a user's
conversation list shows. The raw Messages-API history the agent continues from lives on
`schemas.agent.Conversation`."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel

from intelli_gateway.schemas.tools import JSONValue

Feedback = Literal["up", "down"]


class StoredToolCall(BaseModel):
    """A tool the AI called while answering: what it read (the arguments), not the values."""

    name: str
    args: dict[str, JSONValue]
    summary: str
    duration_ms: float
    is_error: bool


class NewTurn(BaseModel):
    question: str
    answer: str
    model: str | None
    stop_reason: str
    iterations: int
    tool_calls: list[StoredToolCall]
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    duration_ms: float
    created_at: AwareDatetime
    # The site's local time when asked (ISO 8601 with its offset), as the AI was told.
    site_local_time: str


class Turn(NewTurn):
    turn_id: int
    position: int
    feedback: Feedback | None = None
    feedback_comment: str | None = None
    feedback_at: AwareDatetime | None = None


class ConversationSummary(BaseModel):
    conversation_id: str
    site_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    turns: int
