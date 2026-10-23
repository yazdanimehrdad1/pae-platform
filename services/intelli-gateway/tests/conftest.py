import pytest
from fakes import fixed_clock, make_settings

from intelli_gateway.config import Settings
from intelli_gateway.fake_data.knowledge_store import InMemoryKnowledgeStore
from intelli_gateway.fake_data.site_data import FakeSiteDataConnector
from intelli_gateway.tools.catalog import build_local_tools
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.local_provider import LocalToolProvider


@pytest.fixture
def settings() -> Settings:
    return make_settings(ANTHROPIC_API_KEY="test-key")


@pytest.fixture
def site_data() -> FakeSiteDataConnector:
    return FakeSiteDataConnector(clock=fixed_clock)


@pytest.fixture
def knowledge_store() -> InMemoryKnowledgeStore:
    return InMemoryKnowledgeStore.from_fake_sites()


@pytest.fixture
def limits() -> SiteToolLimits:
    return SiteToolLimits(
        max_rows=50, history_samples=12, history_max_days=31, max_text_chars=20_000
    )


@pytest.fixture
def provider(
    site_data: FakeSiteDataConnector,
    knowledge_store: InMemoryKnowledgeStore,
    limits: SiteToolLimits,
) -> LocalToolProvider:
    return LocalToolProvider(
        build_local_tools(site_data, knowledge_store, limits), max_output_chars=20_000
    )
