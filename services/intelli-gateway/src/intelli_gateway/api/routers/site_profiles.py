"""Site profiles for site admins: what the AI knows of each site's facts, the changes waiting in
backend-ot, and approving them (docs/KNOWLEDGE_PLAN.md, section 2). Admins only, with a session."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from intelli_gateway.api.dependencies import (
    get_settings,
    get_site_data,
    get_site_profile_service,
    require_admin,
)
from intelli_gateway.config import Settings
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.schemas.api_models.responses import ErrorResponse
from intelli_gateway.schemas.api_models.site_profiles import (
    ApproveChangesRequest,
    ProfileVersionSummary,
    SiteFunctionTestRunRequest,
    SiteFunctionTestRunResponse,
)
from intelli_gateway.schemas.site_data import SiteFunctionRun
from intelli_gateway.schemas.site_profile import PendingChanges, ProfileVersion, SiteProfileStatus
from intelli_gateway.schemas.users import User
from intelli_gateway.site_profile.functions import run_function
from intelli_gateway.site_profile.service import SiteProfileService

Responses = dict[int | str, dict[str, Any]]
router = APIRouter(
    prefix="/v1",
    tags=["site-profiles"],
    responses={
        401: {"model": ErrorResponse, "description": "Not logged in"},
        403: {"model": ErrorResponse, "description": "Not an admin"},
    },
)
Admin = Annotated[User, Depends(require_admin)]
Profiles = Annotated[SiteProfileService, Depends(get_site_profile_service)]
SiteData = Annotated[SiteDataConnector, Depends(get_site_data)]
AppSettings = Annotated[Settings, Depends(get_settings)]
NOT_FOUND: Responses = {
    404: {"model": ErrorResponse, "description": "Not synced or not onboarded yet"}
}
UPSTREAM: Responses = {503: {"model": ErrorResponse, "description": "backend-ot unreachable"}}


@router.get(
    "/site-profiles",
    response_model=list[SiteProfileStatus],
    summary="Every synced or onboarded site: approved version and pending change count",
)
async def list_site_profiles(admin: Admin, profiles: Profiles) -> list[SiteProfileStatus]:
    del admin
    return await profiles.statuses()


@router.post(
    "/site-profiles/sync",
    response_model=list[SiteProfileStatus],
    responses=UPSTREAM,
    summary="Read every site from backend-ot now (approves nothing)",
)
async def sync_all_site_profiles(admin: Admin, profiles: Profiles) -> list[SiteProfileStatus]:
    del admin
    return await profiles.sync_all()


@router.get(
    "/sites/{site_id}/profile",
    response_model=ProfileVersion,
    responses=NOT_FOUND,
    summary="The site's approved profile: what the AI knows of its facts",
)
async def get_site_profile(site_id: int, admin: Admin, profiles: Profiles) -> ProfileVersion:
    del admin
    return await profiles.get_profile(site_id)


@router.get(
    "/sites/{site_id}/profile/versions",
    response_model=list[ProfileVersionSummary],
    responses=NOT_FOUND,
    summary="Every approved version, newest first",
)
async def list_site_profile_versions(
    site_id: int, admin: Admin, profiles: Profiles
) -> list[ProfileVersionSummary]:
    del admin
    return [ProfileVersionSummary.of(version) for version in await profiles.versions(site_id)]


@router.get(
    "/sites/{site_id}/profile/changes",
    response_model=PendingChanges,
    responses=NOT_FOUND,
    summary="Differences between backend-ot (as last read) and the approved profile",
)
async def get_pending_changes(site_id: int, admin: Admin, profiles: Profiles) -> PendingChanges:
    del admin
    return await profiles.pending_changes(site_id)


@router.post(
    "/sites/{site_id}/profile/sync",
    response_model=PendingChanges,
    responses={**NOT_FOUND, **UPSTREAM},
    summary="Read the site from backend-ot now and list the pending changes",
)
async def sync_site_profile(site_id: int, admin: Admin, profiles: Profiles) -> PendingChanges:
    del admin
    return await profiles.sync_site(site_id)


@router.post(
    "/sites/{site_id}/profile/approve",
    response_model=ProfileVersion,
    responses={
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "backend-ot was read again since"},
        422: {"model": ErrorResponse, "description": "Unknown change id, or nothing to approve"},
    },
    summary="Approve pending changes into a new profile version (onboards a new site)",
)
async def approve_site_profile_changes(
    site_id: int, body: ApproveChangesRequest, admin: Admin, profiles: Profiles
) -> ProfileVersion:
    return await profiles.approve(
        site_id,
        approved_by=admin.email,
        change_ids=body.change_ids,
        expected_fetched_at=body.fetched_at,
    )


@router.post(
    "/sites/{site_id}/functions/{name}/test-run",
    response_model=SiteFunctionTestRunResponse,
    responses={
        404: {"model": ErrorResponse, "description": "No such approved function or device"},
        422: {
            "model": ErrorResponse,
            "description": "Bad window or parameters, or backend-ot refused it",
        },
        **UPSTREAM,
    },
    summary="Run an approved site function exactly as the AI would, and see what it gets",
)
async def test_run_site_function(
    site_id: int,
    name: str,
    body: SiteFunctionTestRunRequest,
    admin: Admin,
    site_data: SiteData,
    settings: AppSettings,
) -> SiteFunctionTestRunResponse:
    del admin
    run = SiteFunctionRun(
        name=name,
        start=body.start,
        end=body.end,
        device_id=body.device_id,
        parameters=body.parameters,
    )
    result = await run_function(
        site_data,
        site_id,
        run,
        max_days=settings.tool_history_max_days,
        sample_count=settings.tool_history_samples,
    )
    return SiteFunctionTestRunResponse(
        function=name, start=body.start, end=body.end, device_id=body.device_id, result=result
    )
