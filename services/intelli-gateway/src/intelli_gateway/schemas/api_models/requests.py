"""Request bodies of the HTTP API."""

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(
        default=None, description="Continue an earlier conversation; omit to start a new one."
    )
