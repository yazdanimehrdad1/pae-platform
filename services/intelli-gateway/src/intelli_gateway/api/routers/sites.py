"""Sites the caller can access, and asking a question about one."""

from fastapi import APIRouter, Depends

from intelli_gateway.agent.service import GatewayService
from intelli_gateway.api.dependencies import get_request_context, get_service
from intelli_gateway.schemas.api_models.requests import AskRequest
from intelli_gateway.schemas.api_models.responses import (
    AskResponse,
    ErrorResponse,
    SiteResponse,
    ToolCallResponse,
    UsageResponse,
)
from intelli_gateway.schemas.context import RequestContext

router = APIRouter(prefix="/v1", tags=["v1"])


@router.get("/sites", response_model=list[SiteResponse], summary="Sites the user can access")
async def list_sites(
    ctx: RequestContext = Depends(get_request_context),
    service: GatewayService = Depends(get_service),
) -> list[SiteResponse]:
    return [
        SiteResponse(
            site_id=site.site_id,
            name=site.name,
            description=site.description,
            capacity_kw=site.capacity_kw,
            timezone=site.timezone,
        )
        for site in await service.list_sites(ctx)
    ]


@router.post(
    "/sites/{site_id}/ask",
    response_model=AskResponse,
    summary="Ask a question about a site",
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def ask(
    site_id: int,
    body: AskRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: GatewayService = Depends(get_service),
) -> AskResponse:
    outcome = await service.ask(ctx, site_id, body.question, body.conversation_id)
    result = outcome.result
    return AskResponse(
        conversation_id=outcome.conversation_id,
        answer=result.answer,
        stop_reason=result.stop_reason,
        iterations=result.iterations,
        model=result.model,
        tool_calls=[
            ToolCallResponse(
                name=call.name,
                args=call.args,
                summary=call.summary,
                duration_ms=call.duration_ms,
                is_error=call.is_error,
            )
            for call in result.tool_calls
        ],
        usage=UsageResponse(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cache_read_input_tokens=result.usage.cache_read_input_tokens,
            cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
        ),
    )
