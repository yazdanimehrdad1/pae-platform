"""Health check endpoints."""

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pymodbus.client import ModbusTcpClient
from sqlalchemy import text

from api.controllers.devices import get_all_devices, get_device_by_id
from cache.connection import check_redis_health, get_redis_client
from config import settings
from db.connection import check_db_health, get_async_engine, get_db_pool
from schemas.api_models import DeviceHealthStatus, HealthResponse, SiteDevicesHealthResponse
from services.modbus.client import ModbusClient

router = APIRouter()

modbus_client = ModbusClient()


@router.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint that verifies API is running."""
    return HealthResponse(
        ok=True,
        host=settings.modbus_host,
        port=settings.modbus_port,
        device_id=settings.modbus_device_id,
        detail="API is healthy"
    )


@router.get("/readyz")
async def readiness_check(response: Response) -> dict[str, Any]:
    """
    Readiness probe for Kubernetes.

    Gates on the hard runtime dependencies — Postgres and Redis — using the
    lightweight shared health checks (a `SELECT 1` and a Redis PING). Returns
    HTTP 503 if either is unreachable so k8s stops routing traffic to the pod.
    Kept intentionally cheap; the detailed /db_health and /redis_health endpoints
    are too heavy to run on every probe interval.
    """
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    ready = db_ok and redis_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": ready,
        "checks": {"database": db_ok, "redis": redis_ok},
    }


@router.get("/health_modbus_client", response_model=HealthResponse)
async def health_modbus_client():
    """Connects to the Modbus server and reads a single register to confirm end-to-end communication."""
    ok, detail = modbus_client.modbus_server_health_check()
    return HealthResponse(
        ok=ok,
        host=settings.modbus_host,
        port=settings.modbus_port,
        device_id=settings.modbus_device_id,
        detail=detail
    )

async def _check_device_reachability(device) -> DeviceHealthStatus:
    host = settings.modbus_host if device.read_from_aggregator else device.host
    port = settings.modbus_port if device.read_from_aggregator else device.port
    timeout = device.timeout or settings.modbus_timeout_s

    t0 = time.monotonic()
    try:
        def _connect():
            client = ModbusTcpClient(host=host, port=port, timeout=timeout)
            try:
                return client.connect()
            finally:
                client.close()

        connected = await asyncio.to_thread(_connect)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        return DeviceHealthStatus(
            device_id=device.device_id,
            name=device.name,
            host=host,
            port=port,
            read_from_aggregator=device.read_from_aggregator,
            poll_enabled=device.poll_enabled,
            reachable=connected,
            latency_ms=latency_ms if connected else None,
            error=None if connected else "TCP connection refused or timed out",
        )
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        return DeviceHealthStatus(
            device_id=device.device_id,
            name=device.name,
            host=host,
            port=port,
            read_from_aggregator=device.read_from_aggregator,
            poll_enabled=device.poll_enabled,
            reachable=False,
            latency_ms=None,
            error=str(exc),
        )


@router.get("/healthz/site/{site_id}", response_model=SiteDevicesHealthResponse)
async def site_devices_health(site_id: int):
    """
    Check Modbus TCP reachability for every active device in a site.

    For devices with read_from_aggregator=true the aggregator host/port is probed;
    otherwise the device's own host/port is used. All devices are checked concurrently.
    """
    try:
        devices = await get_all_devices(site_id)
    except Exception:
        devices = []

    results: list[DeviceHealthStatus] = await asyncio.gather(
        *[_check_device_reachability(d) for d in devices]
    )

    reachable_count = sum(1 for r in results if r.reachable)
    return SiteDevicesHealthResponse(
        site_id=site_id,
        total=len(results),
        reachable=reachable_count,
        unreachable=len(results) - reachable_count,
        devices=list(results),
    )


@router.get("/healthz/site/{site_id}/device/{device_id}", response_model=DeviceHealthStatus)
async def device_health(site_id: int, device_id: int):
    """Check Modbus TCP reachability for a single device."""
    try:
        device = await get_device_by_id(site_id, device_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found in site {site_id}") from None
    return await _check_device_reachability(device)


@router.get("/redis_health")
async def redis_health() -> dict[str, Any]:
    """
    Redis health check endpoint with detailed information.

    Returns:
        Dictionary containing Redis connection status, configuration, and server information
    """
    try:
        client = await get_redis_client()

        # Test connection
        ping_result = await client.ping()

        # Get Redis server info
        info = await client.info()

        # Get connection pool info
        pool = client.connection_pool
        pool_info = {
            "max_connections": pool.max_connections,
            "connection_kwargs": {
                "host": pool.connection_kwargs.get("host"),
                "port": pool.connection_kwargs.get("port"),
                "db": pool.connection_kwargs.get("db"),
            }
        }

        return {
            "status": "healthy" if ping_result else "unhealthy",
            "connected": ping_result,
            "configuration": {
                "host": settings.redis_host,
                "port": settings.redis_port,
                "db": settings.redis_db,
                "max_connections": settings.redis_max_connections,
                "health_check_interval": settings.redis_health_check_interval,
            },
            "server_info": {
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "used_memory_peak_human": info.get("used_memory_peak_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace": {
                    f"db{settings.redis_db}": info.get(f"db{settings.redis_db}", "N/A")
                }
            },
            "connection_pool": pool_info
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "configuration": {
                "host": settings.redis_host,
                "port": settings.redis_port,
                "db": settings.redis_db,
                "max_connections": settings.redis_max_connections,
                "health_check_interval": settings.redis_health_check_interval,
            }
        }


@router.get("/db_health")
async def db_health() -> dict[str, Any]:
    """
    Database health check endpoint with detailed information.

    Returns:
        Dictionary containing database connection status, configuration, and server information
    """
    try:
        # Test connection first
        health_ok = await check_db_health()

        # Get database information
        engine = get_async_engine()
        async with engine.connect() as conn:
            # Get PostgreSQL version
            version_result = await conn.execute(text("SELECT version()"))
            version = version_result.scalar()

            # Get database size
            size_result = await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            db_size = size_result.scalar()

            # Get connection count
            conn_count_result = await conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
            )
            active_connections = conn_count_result.scalar()

            # Get max connections
            max_conn_result = await conn.execute(text("SHOW max_connections"))
            max_connections = max_conn_result.scalar()

            # Check for TimescaleDB extension
            timescale_result = await conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            )
            timescale_version = timescale_result.scalar_one_or_none()

            # Get database name
            db_name_result = await conn.execute(text("SELECT current_database()"))
            db_name = db_name_result.scalar()

            # Get pool info from engine
            pool = engine.pool
            pool_info = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "max_overflow": pool._max_overflow,
            }

            # Try to get asyncpg pool info if available
            asyncpg_pool_info = None
            try:
                asyncpg_pool = await get_db_pool()
                asyncpg_pool_info = {
                    "min_size": asyncpg_pool.get_min_size(),
                    "max_size": asyncpg_pool.get_max_size(),
                    "size": asyncpg_pool.get_size(),
                    "idle_size": asyncpg_pool.get_idle_size(),
                }
            except Exception:
                pass  # asyncpg pool might not be initialized

            server_info = {
                "postgresql_version": version.split(",")[0] if version else "Unknown",
                "database_name": db_name,
                "database_size": db_size,
                "active_connections": active_connections,
                "max_connections": max_connections,
                "connection_usage_percent": round((active_connections / int(max_connections)) * 100, 2) if max_connections else 0,
                "timescaledb_version": timescale_version if timescale_version else None,
            }

            return {
                "status": "healthy" if health_ok else "unhealthy",
                "connected": health_ok,
                "configuration": {
                    "host": settings.postgres_host,
                    "port": settings.postgres_port,
                    "database": settings.postgres_db,
                    "user": settings.postgres_user,
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow,
                },
                "server_info": server_info,
                "connection_pools": {
                    "sqlalchemy": pool_info,
                    "asyncpg": asyncpg_pool_info,
                }
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "configuration": {
                "host": settings.postgres_host,
                "port": settings.postgres_port,
                "database": settings.postgres_db,
                "user": settings.postgres_user,
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
            }
        }
