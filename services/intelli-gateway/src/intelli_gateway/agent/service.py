"""What the API routes call: ask a question about a site, the user's saved conversations and
their feedback, list sites, list tools.

Conversations belong to a real user (the users table) and one site. A user only ever sees their
own conversations, and only for the sites they can access; anything else looks missing (404).
Every conversation is kept (no delete; a retention policy comes later)."""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from intelli_gateway.agent.loop import AgentLoop
from intelli_gateway.interfaces.conversation_store import ConversationStore
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.interfaces.tool_provider import ToolProvider
from intelli_gateway.knowledge.loader import KnowledgeLoader
from intelli_gateway.prompts.system import (
    ANSWER_FORMAT,
    STATIC_INSTRUCTIONS,
    render_site_block,
    render_user_turn,
)
from intelli_gateway.schemas.agent import AgentResult, Conversation, SystemBlock
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.conversations import (
    ConversationSummary,
    Feedback,
    NewTurn,
    StoredToolCall,
    Turn,
)
from intelli_gateway.schemas.site_data import Site
from intelli_gateway.schemas.tools import ToolSpec
from intelli_gateway.utils.exceptions import ForbiddenError, NotFoundError, UnauthorizedError

TITLE_CHARS = 80


@dataclass(frozen=True)
class AskResult:
    conversation_id: str
    turn: Turn
    result: AgentResult


@dataclass(frozen=True)
class ConversationView:
    conversation: Conversation
    turns: list[Turn]


def user_id_of(ctx: RequestContext) -> int:
    """The asking user's id in the users table. Conversations are kept per user, so asking needs
    a real user (a session, or a numeric X-User-Id in dev-header mode)."""
    if not ctx.user_id.isdigit():
        raise UnauthorizedError("log in to ask the AI: conversations are saved per user")
    return int(ctx.user_id)


def title_of(question: str) -> str:
    words = " ".join(question.split())
    return words if len(words) <= TITLE_CHARS else words[: TITLE_CHARS - 1].rstrip() + "…"


def site_local_time(now: datetime, timezone: str) -> str:
    """`now` at the site, ISO 8601 with its offset (UTC if the zone is unknown)."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
    return now.astimezone(zone).isoformat(timespec="seconds")


class GatewayService:
    def __init__(
        self,
        site_data: SiteDataConnector,
        knowledge: KnowledgeLoader,
        conversations: ConversationStore,
        tools: ToolProvider,
        loop: AgentLoop,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._site_data = site_data
        self._knowledge = knowledge
        self._conversations = conversations
        self._tools = tools
        self._loop = loop
        self._clock = clock

    async def list_sites(self, ctx: RequestContext) -> list[Site]:
        return [
            site for site in await self._site_data.list_sites() if ctx.can_access_site(site.site_id)
        ]

    async def list_tools(self) -> list[ToolSpec]:
        return await self._tools.list_tools()

    async def ask(
        self, ctx: RequestContext, site_id: int, question: str, conversation_id: str | None
    ) -> AskResult:
        user_id = user_id_of(ctx)
        if not ctx.can_access_site(site_id):
            raise ForbiddenError("no access to this site")
        site = await self._site_data.get_site(site_id)
        if site is None:
            raise NotFoundError("site not found")
        site_ctx = ctx.for_site(site_id)
        now = self._clock()

        if conversation_id is None:
            conversation = Conversation(
                conversation_id=str(uuid.uuid4()),
                user_id=user_id,
                site_id=site_id,
                title=title_of(question),
                created_at=now,
                updated_at=now,
            )
        else:
            found = await self._conversations.get(conversation_id)
            # Another user's or another site's conversation looks the same as a missing one.
            if found is None or found.user_id != user_id or found.site_id != site_id:
                raise NotFoundError("conversation not found")
            conversation = found

        knowledge = await self._knowledge.load(site_id)
        system = [
            SystemBlock(STATIC_INSTRUCTIONS + "\n" + ANSWER_FORMAT),
            SystemBlock(render_site_block(site, knowledge.text), cache=True),
        ]
        started = time.perf_counter()
        result = await self._loop.run(
            site_ctx,
            system,
            conversation.messages,
            render_user_turn(question, now, site.timezone),
        )
        duration_ms = (time.perf_counter() - started) * 1000
        conversation.messages = result.messages
        conversation.updated_at = now
        turn = await self._conversations.save(
            conversation,
            NewTurn(
                question=question,
                answer=result.answer,
                model=result.model,
                stop_reason=result.stop_reason,
                iterations=result.iterations,
                tool_calls=[
                    StoredToolCall(
                        name=call.name,
                        args=call.args,
                        summary=call.summary,
                        duration_ms=call.duration_ms,
                        is_error=call.is_error,
                    )
                    for call in result.tool_calls
                ],
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cache_read_input_tokens=result.usage.cache_read_input_tokens,
                cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
                duration_ms=round(duration_ms, 1),
                created_at=now,
                site_local_time=site_local_time(now, site.timezone),
            ),
        )
        return AskResult(conversation_id=conversation.conversation_id, turn=turn, result=result)

    async def list_conversations(
        self, ctx: RequestContext, site_id: int | None
    ) -> list[ConversationSummary]:
        """The user's conversations, newest first, only for sites they can access."""
        user_id = user_id_of(ctx)
        return [
            summary
            for summary in await self._conversations.list_for_user(user_id, site_id)
            if ctx.can_access_site(summary.site_id)
        ]

    async def get_conversation(self, ctx: RequestContext, conversation_id: str) -> ConversationView:
        conversation = await self._own_conversation(ctx, conversation_id)
        return ConversationView(conversation, await self._conversations.turns(conversation_id))

    async def set_feedback(
        self,
        ctx: RequestContext,
        conversation_id: str,
        turn_id: int,
        feedback: Feedback | None,
        comment: str | None,
    ) -> Turn:
        await self._own_conversation(ctx, conversation_id)
        turn = await self._conversations.set_feedback(
            conversation_id, turn_id, feedback, comment, self._clock()
        )
        if turn is None:
            raise NotFoundError("answer not found")
        return turn

    async def _own_conversation(self, ctx: RequestContext, conversation_id: str) -> Conversation:
        user_id = user_id_of(ctx)
        conversation = await self._conversations.get(conversation_id)
        if (
            conversation is None
            or conversation.user_id != user_id
            or not ctx.can_access_site(conversation.site_id)
        ):
            raise NotFoundError("conversation not found")
        return conversation
