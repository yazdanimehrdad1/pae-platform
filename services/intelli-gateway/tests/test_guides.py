"""Which guide entries apply to a reading."""

from fakes import FIXED_NOW

from intelli_gateway.knowledge.guides import applicable_guidance
from intelli_gateway.schemas.knowledge import (
    GuideSeverity,
    LimitCondition,
    LimitGuide,
    PointGuide,
    StateGuide,
    StateKind,
)
from intelli_gateway.schemas.site_data import PointValue


def reading(value: float | int | str | None) -> PointValue:
    return PointValue(name="P", device_id=1, value=value, timestamp=FIXED_NOW, age_s=0)


def state(
    kind: StateKind, code: int, severity: GuideSeverity = GuideSeverity.WARNING
) -> StateGuide:
    return StateGuide(kind=kind, code=code, label=f"S{code}", severity=severity, message="m")


def guide(*states: StateGuide, limits: tuple[LimitGuide, ...] = ()) -> PointGuide:
    return PointGuide(
        site_id=1,
        device_id=1,
        point_name="P",
        meaning="m",
        states=states,
        limits=limits,
        updated_at=FIXED_NOW,
    )


class TestApplicableGuidance:
    def test_one_entry_per_set_bit(self) -> None:
        bits = guide(state(StateKind.BIT, 0), state(StateKind.BIT, 2), state(StateKind.BIT, 4))
        matched = applicable_guidance(bits, reading(0b10001))
        assert sorted(entry.label for entry in matched if isinstance(entry, StateGuide)) == [
            "S0",
            "S4",
        ]

    def test_enum_value(self) -> None:
        enum = guide(state(StateKind.ENUM_VALUE, 3), state(StateKind.ENUM_VALUE, 4))
        matched = applicable_guidance(enum, reading(4))
        assert [entry.label for entry in matched if isinstance(entry, StateGuide)] == ["S4"]

    def test_fault_code_zero_matches_nothing(self) -> None:
        codes = guide(state(StateKind.FAULT_CODE, 101))
        assert applicable_guidance(codes, reading(0)) == []
        assert len(applicable_guidance(codes, reading(101))) == 1

    def test_limits_most_severe_first(self) -> None:
        limits = (
            LimitGuide(
                condition=LimitCondition.ABOVE,
                value=60,
                severity=GuideSeverity.WARNING,
                message="derate",
            ),
            LimitGuide(
                condition=LimitCondition.ABOVE,
                value=75,
                severity=GuideSeverity.FAULT,
                message="trip",
            ),
            LimitGuide(
                condition=LimitCondition.BELOW,
                value=0,
                severity=GuideSeverity.WARNING,
                message="frozen",
            ),
        )
        matched = applicable_guidance(guide(limits=limits), reading(80.0))
        assert [entry.severity for entry in matched] == [GuideSeverity.FAULT, GuideSeverity.WARNING]

    def test_non_numeric_value(self) -> None:
        assert applicable_guidance(guide(state(StateKind.ENUM_VALUE, 1)), reading("x")) == []
        assert applicable_guidance(guide(state(StateKind.ENUM_VALUE, 1)), reading(None)) == []
