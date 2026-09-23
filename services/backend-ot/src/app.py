"""
FastAPI application factory.

Creates and configures the FastAPI app instance with routers, middleware, and lifecycle hooks.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.middleware.time_range import validate_time_range

# Router imports
from api.routers import (
    cache,
    csv_exports,
    device_points,
    device_points_readings,
    devices,
    health,
    live_stream_raw_registers,
    live_stream_register_snapshot,
    sites,
)

# Cache connection imports
from cache.connection import check_redis_health, close_redis_client, get_redis_client
from config import settings

# Database connection imports
from db.connection import check_db_health, close_all_db_connections, get_async_engine, get_db_pool
from logger import get_logger, setup_logging
from scheduler.engine import start_scheduler, stop_scheduler

# Setup logging
setup_logging(log_level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage application startup and shutdown."""
    # --- startup ---
    logger.info("Starting PAE Backend OT")

    try:
        await get_redis_client()
        if await check_redis_health():
            logger.info("Redis cache initialized successfully")
        else:
            logger.warning("Redis health check failed, but continuing startup")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")

    try:
        await get_db_pool()
        get_async_engine()
        if await check_db_health():
            logger.info("PostgreSQL database initialized successfully (asyncpg + SQLAlchemy)")
        else:
            logger.warning("Database health check failed, but continuing startup")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    logger.info("Device auto-creation disabled - devices must be created via API endpoints")

    await start_scheduler()

    yield

    # --- shutdown ---
    logger.info("Shutting down PAE Backend OT")
    await stop_scheduler()
    await close_redis_client()
    await close_all_db_connections()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="PAE Backend OT",
        description="Modbus TCP service for polling and storing time-series data",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.middleware("http")(validate_time_range)

    # Mount routers with /api prefix
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(cache.router, prefix="/api", tags=["cache"])
    app.include_router(devices.router, prefix="/api", tags=["devices"])
    app.include_router(sites.router, prefix="/api", tags=["sites"])
    app.include_router(csv_exports.router, prefix="/api", tags=["csv-exports"])
    app.include_router(device_points.router, prefix="/api", tags=["device-points"])
    app.include_router(device_points_readings.router, prefix="/api", tags=["device-point-readings"])
    app.include_router(live_stream_raw_registers.router, prefix="/api", tags=["modbus-live-stream-raw-registers"])
    app.include_router(live_stream_register_snapshot.router, prefix="/api", tags=["modbus-live-stream-register-snapshot"])

    logger.info("FastAPI application created")
    return app


# Create app instance
app = create_app()

