"""The user's saved AI conversations: list, open, and feedback on an answer.

A user sees only their own conversations, and only for sites they can access; anything else is
a 404, like one that doesn't exist. Every conversation is kept: there is no delete (a retention
policy comes later)."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from intelli_gateway.agent.service import GatewayService
from intelli_gateway.api.dependencies import get_request_context, get_service
from intelli_gateway.schemas.api_models.requests import FeedbackRequest
from intelli_gateway.schemas.api_models.responses import (
    ConversationResponse,
    ConversationSummaryResponse,
    ErrorResponse,
    ToolCallResponse,
    TurnResponse,
    UsageResponse,
)
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.conversations import Turn

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])

Responses = dict[int | str, dict[str, Any]]

NOT_FOUND: Responses = {
    404: {"model": ErrorResponse, "description": "No such conversation of yours"}
}
UNAUTHORIZED: Responses = {401: {"model": ErrorResponse, "description": "Not logged in"}}


def turn_response(turn: Turn) -> TurnResponse:
    return TurnResponse(
        turn_id=turn.turn_id,
        position=turn.position,
        question=turn.question,
        answer=turn.answer,
        stop_reason=turn.stop_reason,
        model=turn.model,
        tool_calls=[ToolCallResponse.model_validate(call.model_dump()) for call in turn.tool_calls],
        usage=UsageResponse(
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            cache_read_input_tokens=turn.cache_read_input_tokens,
            cache_creation_input_tokens=turn.cache_creation_input_tokens,
        ),
        duration_ms=turn.duration_ms,
        created_at=turn.created_at,
        site_local_time=turn.site_local_time,
        feedback=turn.feedback,
        feedback_comment=turn.feedback_comment,
        feedback_at=turn.feedback_at,
    )


@router.get(
    "",
    response_model=list[ConversationSummaryResponse],
    responses=UNAUTHORIZED,
    summary="Your AI conversations, newest first",
)
async def list_conversations(
    site_id: int | None = Query(default=None, description="Only this site's conversations"),
    ctx: RequestContext = Depends(get_request_context),
    service: GatewayService = Depends(get_service),
) -> list[ConversationSummaryResponse]:
    return [
        ConversationSummaryResponse.model_validate(summary.model_dump())
        for summary in await service.list_conversations(ctx, site_id)
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    responses={**NOT_FOUND, **UNAUTHORIZED},
    summary="One of your conversations: every question, answer, what the AI read, tokens",
)
async def get_conversation(
    conversation_id: str,
    ctx: RequestContext = Depends(get_request_context),
    service: GatewayService = Depends(get_service),
) -> ConversationResponse:
    view = await service.get_conversation(ctx, conversation_id)
    conversation = view.conversation
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        site_id=conversation.site_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        turns=[turn_response(turn) for turn in view.turns],
    )


@router.put(
    "/{conversation_id}/turns/{turn_id}/feedback",
    response_model=TurnResponse,
    responses={**NOT_FOUND, **UNAUTHORIZED},
    summary="Rate an answer (up / down, optional comment); a null rating clears it",
)
async def set_feedback(
    conversation_id: str,
    turn_id: int,
    body: FeedbackRequest,
    ctx: RequestContext = Depends(get_request_context),
    service: GatewayService = Depends(get_service),
) -> TurnResponse:
    turn = await service.set_feedback(ctx, conversation_id, turn_id, body.rating, body.comment)
    return turn_response(turn)
