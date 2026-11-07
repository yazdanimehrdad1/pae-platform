"""What the service runs on when nothing is injected (production wiring).

Invariant guarded: the running service never uses fictional data. It reads site data only from
backend-ot, through the site profile gate (no setting turns the gate off); it has no engineer
knowledge until the Postgres store exists; it offers no fake forecast source; and it refuses to
start without its own Postgres (DATABASE_URL).
"""

import pytest
from fakes import ScriptedLLMClient, make_settings

from intelli_gateway.knowledge.store import EmptyKnowledgeStore
from intelli_gateway.services.backend_ot.site_data import BackendOtSiteDataConnector
from intelli_gateway.site_profile.gate import ApprovedSiteDataConnector
from intelli_gateway.solar_forecast.registry import SOURCES
from intelli_gateway.utils.exceptions import ConfigurationError
from intelli_gateway.wiring import build_services

# Never connected to: building the engine doesn't open a connection.
UNUSED_DATABASE_URL = "postgresql+asyncpg://user:password@db.invalid:5432/intelli_gateway"


def test_startup_needs_the_database() -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        build_services(make_settings(), llm=ScriptedLLMClient())


async def test_site_data_is_backend_ot_behind_the_gate() -> None:
    services = build_services(
        make_settings(DATABASE_URL=UNUSED_DATABASE_URL), llm=ScriptedLLMClient()
    )
    try:
        assert isinstance(services.site_data, ApprovedSiteDataConnector)
        assert isinstance(services.site_profiles._source, BackendOtSiteDataConnector)  # pyright: ignore[reportPrivateUsage]
        assert services.database is not None
        assert services.backend_ot_client is not None
        loader = services.gateway._knowledge  # pyright: ignore[reportPrivateUsage]
        assert isinstance(loader._store, EmptyKnowledgeStore)  # pyright: ignore[reportPrivateUsage]
    finally:
        await services.aclose()


def test_no_fictional_forecast_source() -> None:
    assert sorted(SOURCES) == ["noaa_hrrr", "open_meteo"]


def test_the_old_switches_are_gone() -> None:
    settings = make_settings(USE_FAKE_DATA="true", SITE_PROFILE_GATE="false")
    assert not hasattr(settings, "use_fake_data")
    assert not hasattr(settings, "site_profile_gate")
