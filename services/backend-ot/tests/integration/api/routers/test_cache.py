"""
Integration tests for the /api/cache admin surface against a real Redis.

Guards set/get/exists/delete round-trips, JSON value types, TTLs, pattern listing, and
clear — all through the key prefix the service applies.
"""

import pytest
from httpx import AsyncClient

from schemas.api_models import CacheGetResponse, CacheSetRequest
from schemas.tests_models import (
    CacheClearResult,
    CacheDeleteResult,
    CacheExistsResult,
    CacheHealthResponse,
    CacheKeysResult,
    CacheSetResult,
)

# Every JSON-serializable shape the cache must round-trip unchanged.
CacheValue = str | int | float | list[int | str | float] | dict[str, dict[str, list[int]]]


async def cache_set(client: AsyncClient, request: CacheSetRequest) -> CacheSetResult:
    response = await client.post("/api/cache/set", json=request.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    return CacheSetResult.model_validate(response.json())


async def cache_exists(client: AsyncClient, key: str) -> bool:
    response = await client.get(f"/api/cache/exists/{key}")
    return CacheExistsResult.model_validate(response.json()).exists


async def cache_delete(client: AsyncClient, key: str) -> CacheDeleteResult:
    response = await client.delete(f"/api/cache/delete/{key}")
    return CacheDeleteResult.model_validate(response.json())


async def cache_keys(client: AsyncClient, **params: str) -> CacheKeysResult:
    response = await client.get("/api/cache/keys", params=params)
    return CacheKeysResult.model_validate(response.json())


class TestCacheRoundTrip:
    @pytest.mark.parametrize("value", ["text", 42, {"nested": {"list": [1, 2]}}, [1, "two", 3.0]])
    async def test_set_then_get_returns_same_value(self, client, value: CacheValue):
        result = await cache_set(client, CacheSetRequest(key="k", value=value))
        assert result.success is True

        fetched = CacheGetResponse.model_validate((await client.get("/api/cache/get/k")).json())
        assert fetched == CacheGetResponse(key="k", value=value, exists=True)

    async def test_missing_key(self, client):
        fetched = CacheGetResponse.model_validate(
            (await client.get("/api/cache/get/absent")).json()
        )
        assert fetched == CacheGetResponse(key="absent", value=None, exists=False)
        assert await cache_exists(client, "absent") is False

    async def test_delete(self, client):
        await cache_set(client, CacheSetRequest(key="k", value=1))
        assert (await cache_delete(client, "k")).success is True
        assert await cache_exists(client, "k") is False
        assert (await cache_delete(client, "k")).success is False

    async def test_ttl_is_applied(self, client):
        await cache_set(client, CacheSetRequest(key="k", value=1, ttl=120))
        [entry] = (await cache_keys(client)).keys
        assert entry.ttl is not None
        assert 0 < entry.ttl <= 120


class TestCacheKeys:
    async def test_pattern_filters_keys(self, client):
        for key in ("poll:1", "poll:2", "other"):
            await cache_set(client, CacheSetRequest(key=key, value=1))
        assert (await cache_keys(client, pattern="poll:*")).count == 2

    async def test_clear_deletes_everything(self, client):
        for key in ("a", "b"):
            await cache_set(client, CacheSetRequest(key=key, value=1))
        cleared = CacheClearResult.model_validate((await client.delete("/api/cache/clear")).json())
        assert cleared.deleted_count == 2
        assert (await cache_keys(client)).count == 0

    async def test_health(self, client):
        health = CacheHealthResponse.model_validate((await client.get("/api/cache/health")).json())
        assert health == CacheHealthResponse(redis_connected=True, status="healthy")
