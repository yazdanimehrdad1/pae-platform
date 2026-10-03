"""Virtual point definitions: how a VIRTUAL point's value is computed from other points.

Two kinds, told apart by ``kind``:

- ``condition``: ordered cases, each a group of conditions combined with ALL/ANY. The first case
  whose group holds sets the output (an integer state); otherwise ``default_output``.
- ``calculation``: an aggregate (sum/avg/min/max) or a two-input difference/ratio, then
  ``result * scale + offset``.

Only the shape and its validation live here. Logic over a definition (the points it reads, its
state labels, evaluating it) is in helpers.virtual_points; that the referenced points exist and fit
(same site, active, not virtual, a bitfield for bit conditions) is checked against the DB when the
point is saved.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

ComparisonOperator = Literal[">", "<", ">=", "<=", "==", "!="]
BitOperator = Literal["bit_set", "bit_clear"]
COMPARISON_OPERATORS: tuple[str, ...] = (">", "<", ">=", "<=", "==", "!=")
BIT_OPERATORS: tuple[str, ...] = ("bit_set", "bit_clear")

# A case's top-level group plus one nested level.
MAX_GROUP_DEPTH = 2
MAX_GROUP_ITEMS = 20
MAX_CASES = 10
MAX_CALCULATION_INPUTS = 20
# Condition outputs are stored as an enum16 point.
MAX_CONDITION_OUTPUT = 65535


class VirtualCondition(BaseModel):
    """One test on one point: compare it to a value or another point, or test one of its bits."""

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"type": "condition", "point_id": 7, "operator": ">=", "value": 20},
        {"type": "condition", "point_id": 71, "operator": "bit_set", "bit": 1},
    ]})

    type: Literal["condition"] = "condition"
    point_id: int = Field(..., description="Point the condition reads")
    operator: ComparisonOperator | BitOperator = Field(
        ...,
        description="Comparison (>, <, >=, <=, ==, !=) or bit test (bit_set, bit_clear). "
        "Enum states compare with == / != on the raw state value.",
    )
    value: float | None = Field(None, description="Comparison: the constant to compare against")
    compare_point_id: int | None = Field(
        None, description="Comparison: another point to compare against, instead of value"
    )
    bit: int | None = Field(None, ge=0, le=63, description="Bit test: the bit index (0 = LSB)")

    @model_validator(mode="after")
    def _check_operands(self) -> VirtualCondition:
        if self.operator in BIT_OPERATORS:
            if self.bit is None:
                raise ValueError(f"operator '{self.operator}' requires bit")
            if self.value is not None or self.compare_point_id is not None:
                raise ValueError(f"operator '{self.operator}' takes bit only, not value or compare_point_id")
        else:
            if (self.value is None) == (self.compare_point_id is None):
                raise ValueError(
                    f"operator '{self.operator}' requires exactly one of value or compare_point_id"
                )
            if self.bit is not None:
                raise ValueError(f"operator '{self.operator}' does not take bit")
        return self


def _group_item_kind(item: object) -> str:
    """Tag of a group item. `type` may be omitted: an item with `items` is a group."""
    if isinstance(item, dict):
        return str(item.get("type") or ("group" if "items" in item else "condition"))
    return str(getattr(item, "type", "condition"))


class VirtualConditionGroup(BaseModel):
    """Conditions and nested groups combined with ALL (and) or ANY (or)."""

    type: Literal["group"] = "group"
    match: Literal["all", "any"] = Field(..., description="all = every item holds, any = at least one")
    items: list[
        Annotated[
            Annotated[VirtualCondition, Tag("condition")] | Annotated[VirtualConditionGroup, Tag("group")],
            Discriminator(_group_item_kind),
        ]
    ] = Field(..., min_length=1, max_length=MAX_GROUP_ITEMS)

    def depth(self) -> int:
        nested = [item.depth() for item in self.items if isinstance(item, VirtualConditionGroup)]
        return 1 + max(nested, default=0)


VirtualConditionGroup.model_rebuild()


class VirtualCase(BaseModel):
    """When ``when`` holds, the point takes ``output``."""

    output: int = Field(..., ge=0, le=MAX_CONDITION_OUTPUT, description="State value this case sets")
    label: str | None = Field(None, max_length=64, description="State name, stored in enum_detail")
    when: VirtualConditionGroup


class VirtualConditionDefinition(BaseModel):
    kind: Literal["condition"]
    cases: list[VirtualCase] = Field(
        ..., min_length=1, max_length=MAX_CASES, description="Checked in order; the first match wins"
    )
    default_output: int = Field(0, ge=0, le=MAX_CONDITION_OUTPUT, description="Output when no case matches")
    default_label: str | None = Field(None, max_length=64, description="State name of default_output")

    @model_validator(mode="after")
    def _check_depth(self) -> VirtualConditionDefinition:
        for index, case in enumerate(self.cases):
            if case.when.depth() > MAX_GROUP_DEPTH:
                raise ValueError(f"case {index + 1}: groups nest at most {MAX_GROUP_DEPTH} levels deep")
        return self


class VirtualCalculationDefinition(BaseModel):
    kind: Literal["calculation"]
    function: Literal["sum", "avg", "min", "max", "difference", "ratio"] = Field(
        ..., description="difference = inputs[0] - inputs[1], ratio = inputs[0] / inputs[1]"
    )
    inputs: list[int] = Field(..., min_length=1, max_length=MAX_CALCULATION_INPUTS, description="Point IDs")
    scale: float = Field(1.0, description="Applied after the function: result * scale + offset")
    offset: float = 0.0

    @model_validator(mode="after")
    def _check_input_count(self) -> VirtualCalculationDefinition:
        if self.function in ("difference", "ratio") and len(self.inputs) != 2:
            raise ValueError(f"function '{self.function}' takes exactly 2 inputs, got {len(self.inputs)}")
        return self


# Either kind, parsed. VirtualPointDefinition is the same union with its discriminator, for
# validating raw JSON (request bodies, the stored virtual_definition column).
VirtualDefinition = VirtualConditionDefinition | VirtualCalculationDefinition

VirtualPointDefinition = Annotated[VirtualDefinition, Field(discriminator="kind")]
