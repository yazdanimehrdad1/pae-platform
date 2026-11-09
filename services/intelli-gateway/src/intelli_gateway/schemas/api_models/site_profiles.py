"""Request and response bodies of the site profile admin routes (api/routers/site_profiles.py)."""

from pydantic import AwareDatetime, BaseModel, Field, JsonValue

from intelli_gateway.schemas.site_data import ParameterValue
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
    functions: int = 0

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
            functions=len(profile.catalog.functions),
        )


class SiteFunctionTestRunRequest(BaseModel):
    start: AwareDatetime = Field(description="Start of the window, ISO 8601 with a UTC offset")
    end: AwareDatetime = Field(description="End of the window, ISO 8601 with a UTC offset")
    device_id: int | None = Field(
        default=None, description="Device functions only: the approved device to run it for"
    )
    parameters: dict[str, ParameterValue] = Field(
        default_factory=dict[str, ParameterValue],
        description="Extra parameters the function declares; omit for their defaults",
    )


class SiteFunctionTestRunResponse(BaseModel):
    """What the AI's run_site_function tool would return for the same request."""

    function: str
    start: AwareDatetime
    end: AwareDatetime
    device_id: int | None = None
    result: dict[str, JsonValue]
