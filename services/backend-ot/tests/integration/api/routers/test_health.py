"""
Integration tests for the health endpoints that don't need a Modbus server.

/healthz must stay unauthenticated and dependency-free (Docker HEALTHCHECK and k8s probes
hit it); /readyz, /db_health and /redis_health must report real connectivity. The Modbus
probes (/health_modbus_client and a *reachable* device) wait for the mock Modbus server;
an unreachable device is covered here because it needs no server.
"""

from config import settings
from integration.factories import create_device, create_site
from schemas.api_models import DeviceHealthStatus, HealthResponse, SiteDevicesHealthResponse
from schemas.tests_models import (
    DbHealthResponse,
    ReadinessChecks,
    ReadinessResponse,
    RedisHealthResponse,
)


class TestLivenessAndReadiness:
    async def test_healthz_is_ok(self, client):
        response = await client.get("/api/healthz")
        assert response.status_code == 200
        assert HealthResponse.model_validate(response.json()).ok is True

    async def test_readyz_reports_db_and_redis(self, client):
        response = await client.get("/api/readyz")
        assert response.status_code == 200
        assert ReadinessResponse.model_validate(response.json()) == ReadinessResponse(
            ready=True, checks=ReadinessChecks(database=True, redis=True)
        )


class TestDependencyHealth:
    async def test_db_health_is_healthy(self, client):
        health = DbHealthResponse.model_validate((await client.get("/api/db_health")).json())
        assert health.status == "healthy", health.error
        assert health.server_info is not None
        assert health.server_info.database_name == settings.postgres_db

    async def test_redis_health_is_healthy(self, client):
        health = RedisHealthResponse.model_validate((await client.get("/api/redis_health")).json())
        assert health.status == "healthy", health.error
        assert health.connected is True


class TestDeviceReachability:
    async def test_unreachable_device_is_reported(self, client):
        site = await create_site(client)
        # Port 1 on localhost refuses immediately; read_from_aggregator=False probes it directly.
        device = await create_device(client, site.site_id, host="127.0.0.1", port=1, timeout=1)

        response = await client.get(f"/api/healthz/site/{site.site_id}/device/{device.device_id}")
        assert response.status_code == 200
        device_health = DeviceHealthStatus.model_validate(response.json())
        assert device_health.reachable is False
        assert device_health.error

        site_health = SiteDevicesHealthResponse.model_validate(
            (await client.get(f"/api/healthz/site/{site.site_id}")).json()
        )
        assert site_health.total == 1
        assert site_health.unreachable == 1

    async def test_unknown_device_is_404(self, client):
        site = await create_site(client)
        response = await client.get(f"/api/healthz/site/{site.site_id}/device/9999")
        assert response.status_code == 404
