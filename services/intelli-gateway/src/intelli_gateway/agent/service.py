"""What the API routes call: ask a question about a site, list sites, list tools."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from intelli_gateway.agent.loop import AgentLoop
from intelli_gateway.interfaces.conversation_store import ConversationStore
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.interfaces.tool_provider import ToolProvider
from intelli_gateway.knowledge.loader import KnowledgeLoader
from intelli_gateway.prompts.system import (
    STATIC_INSTRUCTIONS,
    render_site_block,
    render_user_turn,
)
from intelli_gateway.schemas.agent import AgentResult, Conversation, SystemBlock
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.site_data import Site
from intelli_gateway.schemas.tools import ToolSpec
from intelli_gateway.utils.exceptions import ForbiddenError, NotFoundError


@dataclass(frozen=True)
class AskResult:
    conversation_id: str
    result: AgentResult


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
        if not ctx.can_access_site(site_id):
            raise ForbiddenError("no access to this site")
        site = await self._site_data.get_site(site_id)
        if site is None:
            raise NotFoundError("site not found")
        site_ctx = ctx.for_site(site_id)

        if conversation_id is None:
            conversation = Conversation(
                conversation_id=str(uuid.uuid4()), user_id=ctx.user_id, site_id=site_id
            )
        else:
            found = await self._conversations.get(conversation_id)
            # Another user's or another site's conversation looks the same as a missing one.
            if found is None or found.user_id != ctx.user_id or found.site_id != site_id:
                raise NotFoundError("conversation not found")
            conversation = found

        knowledge = await self._knowledge.load(site_id)
        system = [
            SystemBlock(STATIC_INSTRUCTIONS),
            SystemBlock(render_site_block(site, knowledge.text), cache=True),
        ]
        result = await self._loop.run(
            site_ctx,
            system,
            conversation.messages,
            render_user_turn(question, self._clock(), site.timezone),
        )
        conversation.messages = result.messages
        await self._conversations.save(conversation)
        return AskResult(conversation_id=conversation.conversation_id, result=result)
