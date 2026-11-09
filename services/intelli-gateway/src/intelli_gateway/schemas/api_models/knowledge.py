"""Request and response bodies of the knowledge admin routes (api/routers/knowledge.py)."""

from pydantic import AwareDatetime, BaseModel, Field

from intelli_gateway.schemas.knowledge import (
    DeviceRating,
    KnowledgeChange,
    KnowledgeKind,
    KnowledgeVersion,
    LimitGuide,
    NormalRange,
    SiteKnowledge,
    SiteScriptLinks,
    StateGuide,
)

DRAFT_REVISION = Field(
    default=None,
    ge=0,
    description=(
        "The draft revision you loaded (0 = there was no draft). When someone saved since, "
        "nothing changes (409): reload. Omit to skip the check."
    ),
)


class PointGuideRequest(BaseModel):
    meaning: str = Field(min_length=1, max_length=2000)
    unit_note: str | None = Field(default=None, max_length=500)
    normal_range: NormalRange | None = None
    related_points: list[str] = Field(default_factory=list[str], max_length=20)
    limits: list[LimitGuide] = Field(default_factory=list[LimitGuide], max_length=20)
    states: list[StateGuide] = Field(default_factory=list[StateGuide], max_length=256)
    draft_revision: int | None = DRAFT_REVISION


class DocumentRequest(BaseModel):
    kind: KnowledgeKind
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50_000, description="Pasted text (Markdown).")
    device_id: int | None = None
    point_names: list[str] = Field(default_factory=list[str], max_length=50)
    draft_revision: int | None = DRAFT_REVISION


class SiteScriptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="e.g. 'Overview', 'Startup'.")
    text: str = Field(
        min_length=1, max_length=20_000, description="The information for the AI (Markdown)."
    )
    links: SiteScriptLinks = Field(
        default_factory=SiteScriptLinks,
        description=(
            "Optional: the approved points, site functions, documents and device ratings this "
            "prompt is about, so the AI connects them."
        ),
    )
    draft_revision: int | None = DRAFT_REVISION


class DeviceFactsRequest(BaseModel):
    ratings: list[DeviceRating] = Field(default_factory=list[DeviceRating], max_length=30)
    notes: str | None = Field(default=None, max_length=4000)
    draft_revision: int | None = DRAFT_REVISION


class RevertRequest(BaseModel):
    item_keys: list[str] = Field(min_length=1, description="The draft changes to put back.")
    draft_revision: int | None = DRAFT_REVISION


class PublishRequest(BaseModel):
    draft_revision: int | None = DRAFT_REVISION


class KnowledgeStateResponse(BaseModel):
    """The site's knowledge for an admin: what is published, and the draft (the next publish)."""

    site_id: int
    published_version: int | None
    published_at: AwareDatetime | None
    published_by: str | None
    draft_revision: int = Field(description="0 = no draft: the content is the published one.")
    draft_updated_at: AwareDatetime | None
    draft_updated_by: str | None
    changes: list[KnowledgeChange] = Field(description="What publishing the draft would change.")
    content: SiteKnowledge = Field(description="The draft, or the published knowledge.")


class DocumentCreatedResponse(KnowledgeStateResponse):
    document_id: str


class SiteScriptCreatedResponse(KnowledgeStateResponse):
    script_id: str


class KnowledgeVersionSummary(BaseModel):
    version: int
    published_at: AwareDatetime
    published_by: str
    change_ids: list[str]
    restored_from: int | None
    point_guides: int
    documents: int
    device_facts: int
    site_scripts: int

    @classmethod
    def of(cls, version: KnowledgeVersion) -> "KnowledgeVersionSummary":
        return cls(
            version=version.version,
            published_at=version.published_at,
            published_by=version.published_by,
            change_ids=list(version.change_ids),
            restored_from=version.restored_from,
            point_guides=len(version.content.point_guides),
            documents=len(version.content.documents),
            device_facts=len(version.content.device_facts),
            site_scripts=len(version.content.site_scripts),
        )
