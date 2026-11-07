"""Request and response bodies of the site profile admin routes (api/routers/site_profiles.py)."""

from pydantic import AwareDatetime, BaseModel, Field

from intelli_gateway.schemas.site_profile import ProfileVersion


class ApproveChangesRequest(BaseModel):
    change_ids: list[str] | None = Field(
        default=None,
        description="The pending changes to approve (their change_id). Omit to approve them all.",
    )
    fetched_at: AwareDatetime | None = Field(
        default=None,
        description=(
            "The fetched_at of the pending changes you reviewed. When backend-ot was read again "
            "since, nothing is approved (409): review the changes again."
        ),
    )


class ProfileVersionSummary(BaseModel):
    site_id: int
    version: int
    approved_at: AwareDatetime
    approved_by: str
    change_ids: list[str]
    devices: int
    points: int

    @classmethod
    def of(cls, profile: ProfileVersion) -> "ProfileVersionSummary":
        return cls(
            site_id=profile.site_id,
            version=profile.version,
            approved_at=profile.approved_at,
            approved_by=profile.approved_by,
            change_ids=list(profile.change_ids),
            devices=len(profile.catalog.devices),
            points=len(profile.catalog.points),
        )
