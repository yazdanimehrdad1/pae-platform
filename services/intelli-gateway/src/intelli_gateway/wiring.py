"""Build the object graph from settings: connectors, tools, LLM client, agent loop, service,
and the PV forecast (its site configs, sources, storage and refresh job)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.agent.conversations import InMemoryConversationStore
from intelli_gateway.agent.loop import AgentLoop
from intelli_gateway.agent.service import GatewayService
from intelli_gateway.config import Settings
from intelli_gateway.fake_data.forecast import FakeSiteConfigSource, InMemoryForecastRepository
from intelli_gateway.fake_data.knowledge_store import InMemoryKnowledgeStore
from intelli_gateway.fake_data.site_data import FakeSiteDataConnector
from intelli_gateway.interfaces.forecast_repository import ForecastRepository
from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.llm_client import LLMClient
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.interfaces.site_config_source import SiteConfigSource
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.knowledge.loader import KnowledgeLoader
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_config import BackendOtSiteConfigSource
from intelli_gateway.services.backend_ot.site_data import BackendOtSiteDataConnector
from intelli_gateway.services.claude.client import AnthropicLLMClient
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.services.postgres.forecast_repository import PostgresForecastRepository
from intelli_gateway.solar_forecast.registry import build_sources
from intelli_gateway.solar_forecast.scheduler import ForecastRefreshJob
from intelli_gateway.solar_forecast.service import ForecastService, ForecastSettings
from intelli_gateway.tools.base import ToolDefinition
from intelli_gateway.tools.catalog import build_local_tools
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.forecast_tools import build_forecast_tools
from intelli_gateway.tools.local_provider import LocalToolProvider


@dataclass
class Services:
    gateway: GatewayService
    site_data: SiteDataConnector
    llm: LLMClient
    forecast: ForecastService
    forecast_job: ForecastRefreshJob
    # This service's Postgres; None keeps forecasts in memory. Migrated at startup.
    database: AsyncEngine | None = None
    backend_ot_client: BackendOtClient | None = None

    async def aclose(self) -> None:
        await self.forecast_job.stop()
        await self.llm.aclose()
        await self.site_data.aclose()
        await self.forecast.aclose()  # also disposes the database engine
        if self.backend_ot_client is not None:
            await self.backend_ot_client.aclose()


def _backend_ot_client(settings: Settings) -> BackendOtClient:
    return BackendOtClient(
        base_url=settings.backend_ot_url,
        timeout_s=settings.backend_ot_timeout_s,
        attempts=settings.backend_ot_retries,
    )


def _default_site_data(
    settings: Settings, client: BackendOtClient | None, clock: Callable[[], datetime]
) -> SiteDataConnector:
    if client is None:
        return FakeSiteDataConnector(clock=clock, stale_after_s=settings.data_stale_after_s)
    return BackendOtSiteDataConnector(
        client,
        stale_after_s=settings.data_stale_after_s,
        catalog_ttl_s=settings.backend_ot_catalog_ttl_s,
        clock=clock,
    )


def _default_knowledge_store(settings: Settings) -> KnowledgeStore:
    # The fictional guides belong to the fake sites only: with real data their site ids could
    # match a real site and give it wrong guidance. Until the Postgres store exists, real sites
    # start with no engineer knowledge.
    if settings.use_fake_data:
        return InMemoryKnowledgeStore.from_fake_sites()
    return InMemoryKnowledgeStore([])


def build_services(
    settings: Settings,
    llm: LLMClient | None = None,
    site_data: SiteDataConnector | None = None,
    knowledge_store: KnowledgeStore | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    site_configs: SiteConfigSource | None = None,
    forecast_sources: Sequence[PvForecastSource] | None = None,
    forecast_repository: ForecastRepository | None = None,
) -> Services:
    # One backend-ot client for every backend-ot reader (only with real data).
    backend_ot = None if settings.use_fake_data else _backend_ot_client(settings)
    site_data = site_data or _default_site_data(settings, backend_ot, clock)
    knowledge_store = knowledge_store or _default_knowledge_store(settings)
    llm = llm or AnthropicLLMClient(settings)

    database: AsyncEngine | None = None
    if forecast_repository is None:
        if settings.database_url is not None:
            database = create_database_engine(settings.database_url.get_secret_value())
            forecast_repository = PostgresForecastRepository(database)
        else:
            forecast_repository = InMemoryForecastRepository()
    if site_configs is None:
        site_configs = (
            FakeSiteConfigSource() if backend_ot is None else BackendOtSiteConfigSource(backend_ot)
        )
    forecast = ForecastService(
        sites=site_configs,
        sources=forecast_sources or build_sources(settings, clock),
        repository=forecast_repository,
        settings=ForecastSettings(
            enabled=settings.forecast_enabled,
            horizon_hours=settings.forecast_horizon_hours,
            resolution_minutes=settings.forecast_resolution_minutes,
            refresh_interval_minutes=settings.forecast_fetch_interval_minutes,
            retention_days=settings.forecast_retention_days,
        ),
        clock=clock,
    )
    forecast_job = ForecastRefreshJob(
        forecast,
        settings.forecast_fetch_interval_minutes if settings.forecast_enabled else 0,
    )

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
    if settings.forecast_enabled:
        tools += build_forecast_tools(forecast, clock)
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
    return Services(
        gateway=gateway,
        site_data=site_data,
        llm=llm,
        forecast=forecast,
        forecast_job=forecast_job,
        database=database,
        backend_ot_client=backend_ot,
    )
