"""Build the object graph from settings: connectors, tools, LLM client, agent loop, service."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from intelli_gateway.agent.conversations import InMemoryConversationStore
from intelli_gateway.agent.loop import AgentLoop
from intelli_gateway.agent.service import GatewayService
from intelli_gateway.config import Settings
from intelli_gateway.fake_data.knowledge_store import InMemoryKnowledgeStore
from intelli_gateway.fake_data.site_data import FakeSiteDataConnector
from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.llm_client import LLMClient
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.knowledge.loader import KnowledgeLoader
from intelli_gateway.services.claude.client import AnthropicLLMClient
from intelli_gateway.services.forecast.client import ForecastClient
from intelli_gateway.tools.base import ToolDefinition
from intelli_gateway.tools.catalog import build_local_tools
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.external_tools import build_external_tools
from intelli_gateway.tools.local_provider import LocalToolProvider
from intelli_gateway.utils.exceptions import ConfigurationError


@dataclass
class Services:
    gateway: GatewayService
    site_data: SiteDataConnector
    llm: LLMClient
    forecast_client: ForecastClient | None

    async def aclose(self) -> None:
        await self.llm.aclose()
        await self.site_data.aclose()
        if self.forecast_client is not None:
            await self.forecast_client.aclose()


def build_services(
    settings: Settings,
    llm: LLMClient | None = None,
    site_data: SiteDataConnector | None = None,
    knowledge_store: KnowledgeStore | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Services:
    if not settings.use_fake_data and (site_data is None or knowledge_store is None):
        raise ConfigurationError(
            "USE_FAKE_DATA=false needs the backend-ot and Postgres connectors (phase 2)"
        )
    site_data = site_data or FakeSiteDataConnector(
        clock=clock, stale_after_s=settings.data_stale_after_s
    )
    knowledge_store = knowledge_store or InMemoryKnowledgeStore.from_fake_sites()
    llm = llm or AnthropicLLMClient(settings)

    tools: list[ToolDefinition] = build_local_tools(
        site_data,
        knowledge_store,
        SiteToolLimits(
            max_rows=settings.tool_max_rows,
            history_samples=settings.tool_history_samples,
            history_max_days=settings.tool_history_max_days,
            max_text_chars=settings.tool_max_output_chars,
        ),
    )
    forecast_client: ForecastClient | None = None
    if settings.external_api_url:
        forecast_client = ForecastClient(
            base_url=settings.external_api_url,
            timeout_s=settings.external_api_timeout_s,
            attempts=settings.external_api_retries,
        )
        tools += build_external_tools(site_data, forecast_client)
    provider = LocalToolProvider(tools, max_output_chars=settings.tool_max_output_chars)

    gateway = GatewayService(
        site_data=site_data,
        knowledge=KnowledgeLoader(knowledge_store, llm, settings.knowledge_token_warn),
        conversations=InMemoryConversationStore(),
        tools=provider,
        loop=AgentLoop(
            llm,
            provider,
            max_iterations=settings.agent_max_iterations,
            timeout_s=settings.agent_timeout_s,
        ),
        clock=clock,
    )
    return Services(gateway=gateway, site_data=site_data, llm=llm, forecast_client=forecast_client)
