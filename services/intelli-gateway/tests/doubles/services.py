"""build_test_services: the service's object graph over test doubles only (no Postgres, no
backend-ot, no network): the fictional sites, already onboarded (approved site profiles, so the
AI's gate lets them through), their example guides, in-memory stores and fictional forecast
site configs. Any argument of build_services can be overridden."""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from fakes import fixed_clock

from doubles.conversation_store import InMemoryConversationStore
from doubles.forecast import FakeSiteConfigSource, InMemoryForecastRepository
from doubles.knowledge_authoring_store import InMemoryKnowledgeAuthoringStore
from doubles.knowledge_store import InMemoryKnowledgeStore
from doubles.models import FakeSite
from doubles.site_data import FakeSiteDataConnector
from doubles.site_profile_store import InMemorySiteProfileStore
from doubles.sites import FAKE_SITES
from doubles.user_data_store import InMemoryUserDataStore
from doubles.user_store import InMemoryUserStore
from intelli_gateway.config import Settings
from intelli_gateway.wiring import Services, build_services


def build_test_services(
    settings: Settings,
    clock: Callable[[], datetime] = fixed_clock,
    sites: Sequence[FakeSite] = FAKE_SITES,
    **overrides: Any,
) -> Services:
    defaults: dict[str, Any] = {
        "site_data": FakeSiteDataConnector(sites, clock=clock),
        "knowledge_store": InMemoryKnowledgeStore.from_fake_sites(sites),
        "site_configs": FakeSiteConfigSource(),
        "forecast_repository": InMemoryForecastRepository(),
        "user_store": InMemoryUserStore(),
        "user_data_store": InMemoryUserDataStore(),
        "site_profile_store": InMemorySiteProfileStore.onboarded(sites, clock()),
        "knowledge_authoring_store": InMemoryKnowledgeAuthoringStore(),
        "conversation_store": InMemoryConversationStore(),
    }
    return build_services(settings, clock=clock, **(defaults | overrides))
