"""Engineer-written knowledge: documents (manuals, IM scripts, procedures, notes), point guides
and admin-added device facts. Owned by this service; guides are keyed per site device
(site_id, device_id, point name)."""

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class KnowledgeKind(StrEnum):
    MANUAL = "manual"
    IM_SCRIPT = "im_script"
    PROCEDURE = "procedure"
    EXPERIENCE_NOTE = "experience_note"


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str = Field(default_factory=lambda: uuid4().hex)
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


# --- Admin-added device facts (what backend-ot doesn't hold) ------------------------------------


class DeviceRating(BaseModel):
    """One rating of a device, e.g. BESS energy capacity 80 MWh."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: float
    unit: str


class DeviceFacts(BaseModel):
    model_config = ConfigDict(frozen=True)

    site_id: int
    device_id: int
    ratings: tuple[DeviceRating, ...] = ()
    notes: str | None = None
    author: str | None = None
    updated_at: AwareDatetime


class PromptPointLink(BaseModel):
    """A point a site prompt is about: the site device and the point's name on it."""

    model_config = ConfigDict(frozen=True)

    device_id: int
    point_name: str = Field(min_length=1)


class SitePromptLinks(BaseModel):
    """What a site prompt is about, all optional: approved points (and so their guides), site
    functions (by name), documents (by id) and device ratings (by device). Kept sorted and
    without repeats so an unchanged prompt never shows as an edit."""

    model_config = ConfigDict(frozen=True)

    points: tuple[PromptPointLink, ...] = ()
    functions: tuple[str, ...] = ()
    documents: tuple[str, ...] = ()
    devices: tuple[int, ...] = ()

    @field_validator("points")
    @classmethod
    def _sorted_points(cls, value: tuple[PromptPointLink, ...]) -> tuple[PromptPointLink, ...]:
        unique = {(point.device_id, point.point_name): point for point in value}
        return tuple(unique[key] for key in sorted(unique))

    @field_validator("functions", "documents")
    @classmethod
    def _sorted_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("devices")
    @classmethod
    def _sorted_devices(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(sorted(set(value)))

    def is_empty(self) -> bool:
        return not (self.points or self.functions or self.documents or self.devices)


class SitePrompt(BaseModel):
    """One part of the site's general information for the AI (overview, how the site runs, ...),
    written by an admin as several named texts instead of one long prompt. Kept in `position`
    order (the order they were added); the AI reads them all, first, in its site context."""

    model_config = ConfigDict(frozen=True)

    prompt_id: str = Field(default_factory=lambda: uuid4().hex)
    site_id: int
    name: str
    text: str
    position: int = Field(ge=1)
    links: SitePromptLinks = SitePromptLinks()
    author: str | None = None
    updated_at: AwareDatetime


# Any one item of a site's knowledge (what a draft edit adds, changes or removes).
KnowledgeItem = PointGuide | KnowledgeDocument | DeviceFacts | SitePrompt


# --- A site's knowledge, its draft and its published versions -----------------------------------


class SiteKnowledge(BaseModel):
    """Everything engineers wrote for one site. Point guides name the point within its device
    (`point_name` without the `DEVICE.` prefix), so a device rename doesn't orphan them."""

    model_config = ConfigDict(frozen=True)

    point_guides: tuple[PointGuide, ...] = ()
    documents: tuple[KnowledgeDocument, ...] = ()
    device_facts: tuple[DeviceFacts, ...] = ()
    site_prompts: tuple[SitePrompt, ...] = ()


class KnowledgeDraft(BaseModel):
    """The site's unpublished edits: the whole knowledge as it will be once published.
    `revision` goes up with every save (an edit made against an older revision is refused)."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    revision: int
    content: SiteKnowledge
    updated_at: AwareDatetime
    updated_by: str


class KnowledgeVersion(BaseModel):
    """One publish: what the AI uses, from published_at until the next version."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    version: int
    content: SiteKnowledge
    published_at: AwareDatetime
    published_by: str
    # The items this publish changed (item keys, see KnowledgeChange).
    change_ids: tuple[str, ...] = ()
    # Set when this version restores an earlier one.
    restored_from: int | None = None


class KnowledgeItemKind(StrEnum):
    POINT_GUIDE = "point_guide"
    DOCUMENT = "document"
    DEVICE_FACTS = "device_facts"
    SITE_PROMPT = "site_prompt"


class KnowledgeChange(BaseModel):
    """One draft item that differs from the published knowledge. item_key:
    `point:<device_id>:<point name>`, `document:<document_id>`, `device:<device_id>` or
    `prompt:<prompt_id>`."""

    model_config = ConfigDict(frozen=True)

    item_key: str
    item_kind: KnowledgeItemKind
    kind: Literal["added", "removed", "changed"]
    summary: str


class MissingGuide(BaseModel):
    """An approved status, alarm or fault-code point with no guide (in the draft or published)."""

    model_config = ConfigDict(frozen=True)

    device_id: int
    point_name: str  # within its device
    qualified_name: str
    point_class: str | None = None
    reason: Literal["alarm", "states", "bits"]


class KnowledgeCoverage(BaseModel):
    """What the site's knowledge covers: the onboarding to-do list (on the draft when there is
    one, otherwise on the published knowledge)."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    points: int
    discrete_points: int  # ALARM class, or with enum/bit labels: these need a guide first
    discrete_with_guide: int
    missing_guides: tuple[MissingGuide, ...]
    guides: int
    documents_by_kind: dict[str, int]
    devices: int
    devices_with_facts: int
    # Guides, documents or facts about devices or points the approved profile no longer has:
    # kept, but the AI doesn't use them.
    orphaned: tuple[str, ...]
