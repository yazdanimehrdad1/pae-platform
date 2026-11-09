"""Engineer knowledge for site admins: point guides, documents and device facts, edited as a draft
and published for the whole site at once (docs/KNOWLEDGE_PLAN.md, step 2). Admins only, with a
session. The site must be onboarded (an approved profile): 404 otherwise."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from intelli_gateway.api.dependencies import get_knowledge_service, require_admin
from intelli_gateway.knowledge.service import (
    DocumentContent,
    GuideContent,
    KnowledgeState,
    SiteKnowledgeService,
)
from intelli_gateway.schemas.api_models.knowledge import (
    DeviceFactsRequest,
    DocumentCreatedResponse,
    DocumentRequest,
    KnowledgeStateResponse,
    KnowledgeVersionSummary,
    PointGuideRequest,
    PublishRequest,
    RevertRequest,
    SiteScriptCreatedResponse,
    SiteScriptRequest,
)
from intelli_gateway.schemas.api_models.responses import ErrorResponse
from intelli_gateway.schemas.knowledge import KnowledgeCoverage, KnowledgeVersion
from intelli_gateway.schemas.users import User

Responses = dict[int | str, dict[str, Any]]
router = APIRouter(
    prefix="/v1/sites/{site_id}/knowledge",
    tags=["knowledge"],
    responses={
        401: {"model": ErrorResponse, "description": "Not logged in"},
        403: {"model": ErrorResponse, "description": "Not an admin"},
        404: {"model": ErrorResponse, "description": "Not onboarded, or no such item"},
    },
)
Admin = Annotated[User, Depends(require_admin)]
Knowledge = Annotated[SiteKnowledgeService, Depends(get_knowledge_service)]
EDIT: Responses = {
    409: {"model": ErrorResponse, "description": "The draft changed since draft_revision"},
    422: {"model": ErrorResponse, "description": "Not an approved point/device, or a secret"},
}
DraftRevisionQuery = Annotated[
    int | None, Query(ge=0, description="The draft revision you loaded (0 = no draft).")
]


def _state(state: KnowledgeState) -> KnowledgeStateResponse:
    published, draft = state.published, state.draft
    return KnowledgeStateResponse(
        site_id=state.site_id,
        published_version=published.version if published else None,
        published_at=published.published_at if published else None,
        published_by=published.published_by if published else None,
        draft_revision=state.draft_revision,
        draft_updated_at=draft.updated_at if draft else None,
        draft_updated_by=draft.updated_by if draft else None,
        changes=list(state.changes),
        content=state.working,
    )


def _document(body: DocumentRequest) -> DocumentContent:
    return DocumentContent(
        kind=body.kind,
        title=body.title,
        body=body.body,
        device_id=body.device_id,
        point_names=tuple(body.point_names),
    )


@router.get("", response_model=KnowledgeStateResponse, summary="The draft (or published) knowledge")
async def get_knowledge(site_id: int, admin: Admin, knowledge: Knowledge) -> KnowledgeStateResponse:
    del admin
    return _state(await knowledge.state(site_id))


@router.get(
    "/coverage",
    response_model=KnowledgeCoverage,
    summary="Which status/alarm points still need a guide, devices without facts, orphans",
)
async def get_coverage(site_id: int, admin: Admin, knowledge: Knowledge) -> KnowledgeCoverage:
    del admin
    return await knowledge.coverage(site_id)


@router.put(
    "/point-guides/{device_id}/{point_name}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Write a point's guide into the draft (point name within its device)",
)
async def put_point_guide(
    site_id: int,
    device_id: int,
    point_name: str,
    body: PointGuideRequest,
    admin: Admin,
    knowledge: Knowledge,
) -> KnowledgeStateResponse:
    content = GuideContent(
        meaning=body.meaning,
        unit_note=body.unit_note,
        normal_range=body.normal_range,
        related_points=tuple(body.related_points),
        limits=tuple(body.limits),
        states=tuple(body.states),
    )
    return _state(
        await knowledge.put_point_guide(
            site_id, device_id, point_name, content, admin.email, body.draft_revision
        )
    )


@router.delete(
    "/point-guides/{device_id}/{point_name}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Remove a point's guide in the draft",
)
async def delete_point_guide(
    site_id: int,
    device_id: int,
    point_name: str,
    admin: Admin,
    knowledge: Knowledge,
    draft_revision: DraftRevisionQuery = None,
) -> KnowledgeStateResponse:
    return _state(
        await knowledge.delete_point_guide(
            site_id, device_id, point_name, admin.email, draft_revision
        )
    )


@router.post(
    "/documents",
    response_model=DocumentCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses=EDIT,
    summary="Add a document (manual, IM script, procedure, experience note) to the draft",
)
async def create_document(
    site_id: int, body: DocumentRequest, admin: Admin, knowledge: Knowledge
) -> DocumentCreatedResponse:
    state, document_id = await knowledge.create_document(
        site_id, _document(body), admin.email, body.draft_revision
    )
    return DocumentCreatedResponse(**_state(state).model_dump(), document_id=document_id)


@router.put(
    "/documents/{document_id}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Change a document in the draft",
)
async def update_document(
    site_id: int, document_id: str, body: DocumentRequest, admin: Admin, knowledge: Knowledge
) -> KnowledgeStateResponse:
    return _state(
        await knowledge.update_document(
            site_id, document_id, _document(body), admin.email, body.draft_revision
        )
    )


@router.delete(
    "/documents/{document_id}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Remove a document in the draft",
)
async def delete_document(
    site_id: int,
    document_id: str,
    admin: Admin,
    knowledge: Knowledge,
    draft_revision: DraftRevisionQuery = None,
) -> KnowledgeStateResponse:
    return _state(
        await knowledge.delete_document(site_id, document_id, admin.email, draft_revision)
    )


@router.post(
    "/site-scripts",
    response_model=SiteScriptCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses=EDIT,
    summary="Add a site script (general information about the site) after the others, to the draft",
)
async def create_site_script(
    site_id: int, body: SiteScriptRequest, admin: Admin, knowledge: Knowledge
) -> SiteScriptCreatedResponse:
    state, script_id = await knowledge.create_site_script(
        site_id, body.name, body.text, admin.email, body.draft_revision, body.links
    )
    return SiteScriptCreatedResponse(**_state(state).model_dump(), script_id=script_id)


@router.put(
    "/site-scripts/{script_id}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Change a site script's name, text and links in the draft",
)
async def update_site_script(
    site_id: int, script_id: str, body: SiteScriptRequest, admin: Admin, knowledge: Knowledge
) -> KnowledgeStateResponse:
    return _state(
        await knowledge.update_site_script(
            site_id,
            script_id,
            body.name,
            body.text,
            admin.email,
            body.draft_revision,
            body.links,
        )
    )


@router.delete(
    "/site-scripts/{script_id}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Remove a site script in the draft",
)
async def delete_site_script(
    site_id: int,
    script_id: str,
    admin: Admin,
    knowledge: Knowledge,
    draft_revision: DraftRevisionQuery = None,
) -> KnowledgeStateResponse:
    return _state(
        await knowledge.delete_site_script(site_id, script_id, admin.email, draft_revision)
    )


@router.put(
    "/device-facts/{device_id}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Write a device's ratings and notes into the draft",
)
async def put_device_facts(
    site_id: int, device_id: int, body: DeviceFactsRequest, admin: Admin, knowledge: Knowledge
) -> KnowledgeStateResponse:
    return _state(
        await knowledge.put_device_facts(
            site_id, device_id, body.ratings, body.notes, admin.email, body.draft_revision
        )
    )


@router.delete(
    "/device-facts/{device_id}",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Remove a device's ratings and notes in the draft",
)
async def delete_device_facts(
    site_id: int,
    device_id: int,
    admin: Admin,
    knowledge: Knowledge,
    draft_revision: DraftRevisionQuery = None,
) -> KnowledgeStateResponse:
    return _state(
        await knowledge.delete_device_facts(site_id, device_id, admin.email, draft_revision)
    )


@router.post(
    "/draft/revert",
    response_model=KnowledgeStateResponse,
    responses=EDIT,
    summary="Put some draft changes back as published",
)
async def revert_draft_items(
    site_id: int, body: RevertRequest, admin: Admin, knowledge: Knowledge
) -> KnowledgeStateResponse:
    return _state(await knowledge.revert(site_id, body.item_keys, admin.email, body.draft_revision))


@router.delete("/draft", response_model=KnowledgeStateResponse, summary="Discard the whole draft")
async def discard_draft(site_id: int, admin: Admin, knowledge: Knowledge) -> KnowledgeStateResponse:
    del admin
    return _state(await knowledge.discard_draft(site_id))


@router.post(
    "/publish",
    response_model=KnowledgeVersion,
    responses={
        409: {"model": ErrorResponse, "description": "The draft changed since draft_revision"},
        422: {"model": ErrorResponse, "description": "Nothing to publish"},
    },
    summary="Publish the whole draft: the AI uses it from now on",
)
async def publish(
    site_id: int, body: PublishRequest, admin: Admin, knowledge: Knowledge
) -> KnowledgeVersion:
    return await knowledge.publish(site_id, admin.email, body.draft_revision)


@router.get(
    "/versions",
    response_model=list[KnowledgeVersionSummary],
    summary="Every published version, newest first",
)
async def list_versions(
    site_id: int, admin: Admin, knowledge: Knowledge
) -> list[KnowledgeVersionSummary]:
    del admin
    return [KnowledgeVersionSummary.of(version) for version in await knowledge.versions(site_id)]


@router.delete(
    "/versions",
    response_model=list[KnowledgeVersionSummary],
    responses={
        422: {"model": ErrorResponse, "description": "One of them is the version the AI uses"}
    },
    summary="Delete older published versions (never the one the AI uses); the versions left",
)
async def delete_versions(
    site_id: int,
    versions: Annotated[
        list[int], Query(alias="version", min_length=1, description="Repeat for each version.")
    ],
    admin: Admin,
    knowledge: Knowledge,
) -> list[KnowledgeVersionSummary]:
    remaining = await knowledge.delete_versions(site_id, versions, admin.email)
    return [KnowledgeVersionSummary.of(version) for version in remaining]


@router.get("/versions/{version}", response_model=KnowledgeVersion, summary="One published version")
async def get_version(
    site_id: int, version: int, admin: Admin, knowledge: Knowledge
) -> KnowledgeVersion:
    del admin
    return await knowledge.version(site_id, version)


@router.post(
    "/versions/{version}/restore",
    response_model=KnowledgeVersion,
    responses={
        409: {"model": ErrorResponse, "description": "There is a draft: publish or discard it"},
        422: {"model": ErrorResponse, "description": "That version is already in use"},
    },
    summary="Publish an earlier version's content again, as a new version",
)
async def restore_version(
    site_id: int, version: int, admin: Admin, knowledge: Knowledge
) -> KnowledgeVersion:
    return await knowledge.restore(site_id, version, admin.email)
