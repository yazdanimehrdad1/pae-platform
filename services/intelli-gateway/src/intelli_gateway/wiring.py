"""Build the object graph from settings: connectors, tools, LLM client, agent loop, service,
the site profiles (the AI's gate to site data) and the PV forecast.

Runtime always uses real systems: site data from backend-ot, storage in this service's
Postgres (DATABASE_URL is required). Tests pass their doubles (tests/doubles/) as arguments."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.agent.conversations import InMemoryConversationStore
from intelli_gateway.agent.loop import AgentLoop
from intelli_gateway.agent.service import GatewayService
from intelli_gateway.auth.service import AuthService, SessionSettings
from intelli_gateway.config import Settings
from intelli_gateway.interfaces.forecast_repository import ForecastRepository
from intelli_gateway.interfaces.knowledge_authoring_store import KnowledgeAuthoringStore
from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.llm_client import LLMClient
from intelli_gateway.interfaces.pv_forecast_source import PvForecastSource
from intelli_gateway.interfaces.site_config_source import SiteConfigSource
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.interfaces.site_profile_store import SiteProfileStore
from intelli_gateway.interfaces.user_data_store import UserDataStore
from intelli_gateway.interfaces.user_store import UserStore
from intelli_gateway.knowledge.loader import KnowledgeLoader
from intelli_gateway.knowledge.published_store import PublishedKnowledgeStore
from intelli_gateway.knowledge.service import SiteKnowledgeService
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_config import BackendOtSiteConfigSource
from intelli_gateway.services.backend_ot.site_data import BackendOtSiteDataConnector
from intelli_gateway.services.claude.client import AnthropicLLMClient
from intelli_gateway.services.postgres.database import create_database_engine
from intelli_gateway.services.postgres.forecast_repository import PostgresForecastRepository
from intelli_gateway.services.postgres.knowledge_authoring_store import (
    PostgresKnowledgeAuthoringStore,
)
from intelli_gateway.services.postgres.site_profile_store import PostgresSiteProfileStore
from intelli_gateway.services.postgres.user_data_store import PostgresUserDataStore
from intelli_gateway.services.postgres.user_store import PostgresUserStore
from intelli_gateway.site_profile.gate import ApprovedSiteDataConnector
from intelli_gateway.site_profile.scheduler import SiteProfileSyncJob
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.solar_forecast.registry import build_sources
from intelli_gateway.solar_forecast.scheduler import ForecastRefreshJob
from intelli_gateway.solar_forecast.service import ForecastService, ForecastSettings
from intelli_gateway.tools.base import ToolDefinition
from intelli_gateway.tools.catalog import build_local_tools
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.forecast_tools import build_forecast_tools
from intelli_gateway.tools.local_provider import LocalToolProvider
from intelli_gateway.user_data.service import UserDataService
from intelli_gateway.utils.exceptions import ConfigurationError


@dataclass
class Services:
    gateway: GatewayService
    site_data: SiteDataConnector
    llm: LLMClient
    forecast: ForecastService
    forecast_job: ForecastRefreshJob
    auth: AuthService
    user_data: UserDataService
    site_profiles: SiteProfileService
    site_profile_job: SiteProfileSyncJob
    knowledge: SiteKnowledgeService
    # This service's Postgres (None only when tests passed every store). Migrated at startup.
    database: AsyncEngine | None = None
    backend_ot_client: BackendOtClient | None = None

    async def aclose(self) -> None:
        await self.forecast_job.stop()
        await self.site_profile_job.stop()
        await self.llm.aclose()
        await self.site_data.aclose()
        await self.forecast.aclose()
        if self.database is not None:
            await self.database.dispose()  # safe after the forecast repository disposed it
        if self.backend_ot_client is not None:
            await self.backend_ot_client.aclose()


def _backend_ot_client(settings: Settings) -> BackendOtClient:
    return BackendOtClient(
        base_url=settings.backend_ot_url,
        timeout_s=settings.backend_ot_timeout_s,
        attempts=settings.backend_ot_retries,
    )


def _database(settings: Settings) -> AsyncEngine:
    if settings.database_url is None:
        raise ConfigurationError(
            "DATABASE_URL is required: users, site profiles and forecasts are stored in this "
            "service's Postgres"
        )
    return create_database_engine(settings.database_url.get_secret_value())


def build_services(
    settings: Settings,
    llm: LLMClient | None = None,
    site_data: SiteDataConnector | None = None,
    knowledge_store: KnowledgeStore | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    site_configs: SiteConfigSource | None = None,
    forecast_sources: Sequence[PvForecastSource] | None = None,
    forecast_repository: ForecastRepository | None = None,
    user_store: UserStore | None = None,
    user_data_store: UserDataStore | None = None,
    site_profile_store: SiteProfileStore | None = None,
    knowledge_authoring_store: KnowledgeAuthoringStore | None = None,
) -> Services:
    # One backend-ot client for every backend-ot reader (none when tests passed both readers).
    backend_ot = None
    if site_data is None or site_configs is None:
        backend_ot = _backend_ot_client(settings)
    # The ungated connector: only the site profile service reads it directly.
    source_data = site_data
    if source_data is None:
        assert backend_ot is not None
        source_data = BackendOtSiteDataConnector(
            backend_ot,
            stale_after_s=settings.data_stale_after_s,
            catalog_ttl_s=settings.backend_ot_catalog_ttl_s,
            clock=clock,
        )
    if site_configs is None:
        assert backend_ot is not None
        site_configs = BackendOtSiteConfigSource(backend_ot)
    llm = llm or AnthropicLLMClient(settings)

    database: AsyncEngine | None = None
    if (
        forecast_repository is None
        or user_store is None
        or user_data_store is None
        or site_profile_store is None
        or knowledge_authoring_store is None
    ):
        database = _database(settings)
        forecast_repository = forecast_repository or PostgresForecastRepository(database)
        user_store = user_store or PostgresUserStore(database)
        user_data_store = user_data_store or PostgresUserDataStore(database)
        site_profile_store = site_profile_store or PostgresSiteProfileStore(database)
        knowledge_authoring_store = knowledge_authoring_store or PostgresKnowledgeAuthoringStore(
            database
        )
    user_data = UserDataService(user_data_store, clock)
    site_profiles = SiteProfileService(
        site_profile_store, source_data, clock, cache_ttl_s=settings.site_profile_cache_ttl_s
    )
    site_profile_job = SiteProfileSyncJob(
        site_profiles, settings.site_profile_sync_interval_minutes
    )
    # The AI (tools, the agent service) reads only approved sites, devices and points.
    site_data = ApprovedSiteDataConnector(source_data, site_profiles)
    # Engineer knowledge: admins edit drafts and publish; the AI reads the published version.
    knowledge = SiteKnowledgeService(
        knowledge_authoring_store,
        site_profiles,
        clock,
        cache_ttl_s=settings.site_profile_cache_ttl_s,
    )
    knowledge_store = knowledge_store or PublishedKnowledgeStore(knowledge, site_profiles)
    auth = AuthService(
        user_store,
        clock,
        SessionSettings(ttl=timedelta(days=settings.session_ttl_days)),
        demo_email=settings.demo_user_email,
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
            series_max_hours=settings.tool_series_max_hours,
            series_interval_minutes=settings.tool_series_interval_minutes,
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
        auth=auth,
        user_data=user_data,
        site_profiles=site_profiles,
        site_profile_job=site_profile_job,
        knowledge=knowledge,
        database=database,
        backend_ot_client=backend_ot,
    )
