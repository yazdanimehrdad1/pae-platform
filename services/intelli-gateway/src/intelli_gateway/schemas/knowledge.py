"""Engineer-written knowledge: documents (manuals, IM scripts, notes) and point guides.
Owned by this service; guides are keyed per site device (site_id, device_id, point name)."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict


class KnowledgeKind(StrEnum):
    MANUAL = "manual"
    IM_SCRIPT = "im_script"
    EXPERIENCE_NOTE = "experience_note"


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    site_id: int
    kind: KnowledgeKind
    title: str
    body: str
    device_id: int | None = None
    # Experience notes: the points the note is about (lets search find it by point).
    point_names: tuple[str, ...] = ()
    author: str | None = None
    updated_at: AwareDatetime


class GuideSeverity(StrEnum):
    FAULT = "fault"  # the equipment stopped or must be stopped
    WARNING = "warning"  # runs, but degraded or at risk
    INFO = "info"  # normal or informational state


class StateKind(StrEnum):
    ENUM_VALUE = "enum_value"
    BIT = "bit"
    FAULT_CODE = "fault_code"  # a vendor fault code read as a number


class StateGuide(BaseModel):
    """What one enum value, bit or vendor fault code means, and what to do about it."""

    model_config = ConfigDict(frozen=True)

    kind: StateKind
    code: int  # the enum value, the bit index (0 = LSB) or the fault code
    label: str
    severity: GuideSeverity
    message: str  # what the engineer sees or is told, one line
    meaning: str | None = None
    probable_causes: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    related_points: tuple[str, ...] = ()
    safety_note: str | None = None


class LimitCondition(StrEnum):
    ABOVE = "above"
    BELOW = "below"


class LimitGuide(BaseModel):
    """A limit on an analog point, e.g. cabinet temperature above 60 degC = derating."""

    model_config = ConfigDict(frozen=True)

    condition: LimitCondition
    value: float
    severity: GuideSeverity
    message: str
    probable_causes: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()

    def applies_to(self, reading: float) -> bool:
        if self.condition is LimitCondition.ABOVE:
            return reading > self.value
        return reading < self.value


class NormalRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    min: float | None = None
    max: float | None = None
    note: str | None = None


class PointGuide(BaseModel):
    """Engineer-written guide for one point of one site device."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    device_id: int
    point_name: str
    meaning: str
    unit_note: str | None = None
    normal_range: NormalRange | None = None
    related_points: tuple[str, ...] = ()
    limits: tuple[LimitGuide, ...] = ()
    states: tuple[StateGuide, ...] = ()
    author: str | None = None
    updated_at: AwareDatetime

    def find_state(self, code: int | None = None, label: str | None = None) -> StateGuide | None:
        for state in self.states:
            if code is not None and state.code == code:
                return state
            if label is not None and state.label.lower() == label.lower():
                return state
        return None
