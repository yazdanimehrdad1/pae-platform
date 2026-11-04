"""Request bodies of the HTTP API."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from intelli_gateway.schemas.tools import JSONValue


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(
        default=None, description="Continue an earlier conversation; omit to start a new one."
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254, description="Case-insensitive.")
    password: str = Field(min_length=1, max_length=1024)


class PreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: JSONValue = Field(description="Any JSON value, at most 64 KiB serialized.")


class NoteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=10_000)
    created_at: AwareDatetime | None = Field(
        default=None, description="Only to keep the dates of a note imported from the browser."
    )
    updated_at: AwareDatetime | None = Field(default=None, description="As created_at.")


class NoteUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=10_000)


class TrendOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trend_ids: list[int] = Field(description="Every one of your trend ids, in the new order.")


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        min_length=1,
        max_length=254,
        description="The sign-in name; stored lower-case (name@domain.tld)",
    )
    display_name: str = Field(min_length=1, max_length=200)
    role: Literal["engineer", "admin", "monitor"]
    password: str = Field(min_length=10, max_length=1024)


class UserUpdateRequest(BaseModel):
    """Only the fields given change."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Literal["engineer", "admin", "monitor"] | None = None
    disabled: bool | None = Field(default=None, description="true also ends the user's sessions.")


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=10, max_length=1024)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=10, max_length=1024)
