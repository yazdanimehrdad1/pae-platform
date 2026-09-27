"""FastAPI application factory. Every route lives under /api and declares a response_model.

Startup connects to Postgres (DATABASE_URL) and applies migrations, seeds the shipped defaults
into an empty database, loads the active site (ACTIVE_SITE overrides the stored choice), builds
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
from powerflow.core.site_library import SiteLibrary, seed_defaults
from powerflow.errors import SiteConfigError
from powerflow.interfaces.base import AdapterContext, AdapterRegistry
from powerflow.interfaces.http.adapter import HttpAdapter, build_router, install_error_handlers
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.settings import settings
from powerflow.storage import ConfigRepository, ProfileStore
from powerflow.storage.defaults import read_defaults
from powerflow.storage.postgres import (
    PostgresConfigRepository,
    create_database_engine,
    migrate,
    wait_for_database,
)

# The OpenAPI `info.version` is this service's contract version: bump it for a breaking change
# (see contracts/README.md).
API_VERSION = "0.1.0"
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
    site_config_dir: Path | None = None, repository: ConfigRepository | None = None
) -> FastAPI:
    """site_config_dir overrides SITE_CONFIG_DIR; repository replaces Postgres (tests pass an
    InMemoryConfigRepository)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        _configure_logging(settings.log_level)
        defaults_dir = site_config_dir or settings.resolved_site_config_dir()
        store = repository or await _open_repository()
        if await store.is_empty():
            await seed_defaults(store, read_defaults(defaults_dir))
            logger.info("empty database: seeded the defaults from %s", defaults_dir)
        active_site = settings.active_site or await store.get_active_site()
        if active_site is None:
            raise SiteConfigError("no active site: POST /api/sites/{name}/activate is needed")
        config = await store.get_site(active_site)
        profile_store = ProfileStore(defaults_dir / "profiles")
        runtime = SiteRuntime.build(config, profile_store, PandapowerSolver)
        engine = Engine(runtime, PandapowerSolver, profile_store)
        setpoints = SetpointService(engine)
        library = SiteLibrary(store, profile_store, engine, defaults_dir, active_site)
        context = AdapterContext(
            engine=engine,
            points=PointRegistry(engine, setpoints),
            setpoints=setpoints,
            library=library,
        )
        adapters = AdapterRegistry()
        adapters.register(HttpAdapter.name, lambda _: HttpAdapter())
        app.state.context = context
        app.state.adapters = adapters
        await adapters.start_enabled(config.interfaces, context)
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
