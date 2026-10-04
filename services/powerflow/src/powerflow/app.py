"""FastAPI application factory. Every route lives under /api and declares a response_model.

Startup connects to Postgres (DATABASE_URL) and applies migrations (a fresh database gets the
default sites from one), loads the active site (ACTIVE_SITE overrides the stored choice), builds
the engine and the protocol-neutral data layer, starts the enabled interface adapters, and starts
the real-time loop if `simulation.autostart` is set.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from powerflow.core.engine import Engine
from powerflow.core.point_registry import PointRegistry
from powerflow.core.runtime import SiteRuntime
from powerflow.core.setpoints import SetpointService
from powerflow.core.site_library import SiteLibrary
from powerflow.errors import SiteConfigError
from powerflow.interfaces.base import AdapterContext, AdapterRegistry
from powerflow.interfaces.http.adapter import HttpAdapter, build_router, install_error_handlers
from powerflow.interfaces.modbus.adapter import ModbusAdapter
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.point_standard import load_point_standard
from powerflow.settings import settings
from powerflow.site_config import SiteConfig
from powerflow.storage import ConfigRepository, ProfileStore
from powerflow.storage.postgres import (
    PostgresConfigRepository,
    create_database_engine,
    migrate,
    wait_for_database,
)

# The OpenAPI `info.version` is this service's contract version: bump it for a breaking change
# (see contracts/README.md).
API_VERSION = "0.2.0"
DESCRIPTION = """\
Grid-connected microgrid power flow simulator (pandapower, balanced positive sequence,
quasi-static). The EMS writes setpoints; every step the simulator applies the asset limits,
solves the network and publishes a measurement snapshot.

**Sign conventions**
- BESS / PV P and Q: generator convention. P > 0 injects (BESS discharging, PV producing),
  P < 0 is a charging BESS. Q > 0 injects vars.
- Load P and Q: P > 0 consumes, Q > 0 consumes vars (lagging).
- POI: P > 0 exports to the utility, P < 0 imports. The same for Q.
- Transformers: P/Q > 0 flows toward the grid (LV → HV).
- pf = |P|/S, signed with Q in the element's own convention.

**Units:** kW, kvar, kVA, kWh, kV (line-to-line), pu where noted, s.

**Points:** `<asset_type>.<asset_id>.<point>`, listed at GET /api/points.
"""

logger = logging.getLogger("powerflow")


def _configure_logging(level: str) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.setLevel(level.upper())


async def _open_repository() -> ConfigRepository:
    """Postgres from DATABASE_URL: wait until it answers, then apply migrations."""
    database = create_database_engine(settings.database_url)
    await wait_for_database(database)
    await migrate(database)
    return PostgresConfigRepository(database)


def create_app(
    profiles_dir: Path | None = None, repository: ConfigRepository | None = None
) -> FastAPI:
    """profiles_dir overrides PROFILES_DIR; repository replaces Postgres (tests pass an
    InMemoryConfigRepository, usually `.with_default_sites()`)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        _configure_logging(settings.log_level)
        store = repository or await _open_repository()
        # ACTIVE_SITE overrides the stored choice for this run only (the database keeps its own).
        active_site = settings.active_site or await store.get_active_site()
        if active_site is None:
            raise SiteConfigError(
                "no active site is stored: set ACTIVE_SITE to one of the stored sites"
            )
        config = await store.get_site(active_site)
        profile_store = ProfileStore(profiles_dir or settings.resolved_profiles_dir())
        runtime = SiteRuntime.build(config, profile_store, PandapowerSolver)
        engine = Engine(runtime, PandapowerSolver, profile_store)
        setpoints = SetpointService(engine)
        library = SiteLibrary(store, profile_store, engine, active_site)
        context = AdapterContext(
            engine=engine,
            points=PointRegistry(engine, setpoints),
            setpoints=setpoints,
            library=library,
            point_standard=load_point_standard(settings.resolved_point_standard_dir()),
        )
        adapters = AdapterRegistry()
        adapters.register(HttpAdapter.name, lambda _: HttpAdapter())
        adapters.register(
            ModbusAdapter.name,
            lambda adapter_context: ModbusAdapter(
                adapter_context,
                settings.modbus_host,
                settings.modbus_port,
                settings.modbus_unit_id,
            ),
        )
        app.state.context = context
        app.state.adapters = adapters

        async def restart_interfaces(new_config: SiteConfig) -> None:
            await adapters.reconcile(new_config.interfaces, context)

        library.on_config_replaced = restart_interfaces
        await adapters.reconcile(config.interfaces, context)
        logger.info("site %r (%s) loaded", active_site, config.site.name)
        if config.simulation.autostart:
            await engine.start()
        try:
            yield
        finally:
            await engine.shutdown()
            await adapters.stop_all()
            await store.close()

    app = FastAPI(
        title="powerflow", description=DESCRIPTION, version=API_VERSION, lifespan=lifespan
    )
    app.include_router(build_router(API_VERSION), prefix="/api")
    install_error_handlers(app)
    return app


app = create_app()
