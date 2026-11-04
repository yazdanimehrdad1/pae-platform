"""What a user keeps across browsers and devices: preferences, saved Historian trends, notes.

A trend mirrors web-plusdas's `Trend` (features/historian/types.ts): only its definition, never
readings. These models are both the stored shape and the API bodies (the API's request models
add `extra="forbid"`). Times are timezone-aware UTC.
"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from intelli_gateway.schemas.tools import JSONValue

PREFERENCE_KEY_PATTERN = r"^[a-z][a-z0-9_.-]{0,63}$"
# Bounds that keep one user's data small; the UI has tighter limits of its own.
MAX_PREFERENCES = 100
MAX_PREFERENCE_BYTES = 64 * 1024
MAX_TRENDS = 50
MAX_NOTES = 200

AxisScale = Literal["per-unit", "per-point", "shared"]
LineDash = Literal["solid", "dashed", "dotted"]


class Preference(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    value: JSONValue
    updated_at: AwareDatetime


class SeriesStyle(BaseModel):
    """What the user changed in how one selection is drawn; a missing field uses the default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    color: str | None = Field(default=None, max_length=32)
    dash: LineDash | None = None
    width: int | None = Field(default=None, ge=1, le=3)


class TrendDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64)
    points: list[str] = Field(
        default_factory=list[str],
        max_length=50,
        description="Historian selection ids, as web-plusdas builds them.",
    )
    scale: AxisScale | None = Field(default=None, description="null: the default (per unit).")
    styles: dict[str, SeriesStyle] | None = Field(
        default=None, description="By selection id; null or a missing entry: the defaults."
    )


class SavedTrend(TrendDefinition):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int
    position: int = Field(description="The user's order, 0 first.")
    created_at: AwareDatetime
    updated_at: AwareDatetime


class Note(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    content: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
