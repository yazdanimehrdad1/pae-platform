"""Cache test endpoints for manual testing."""

from fastapi import APIRouter

from cache import cache, check_redis_health
from schemas.api_models import CacheGetResponse, CacheSetRequest

router = APIRouter()


@router.get("/cache/health")
async def cache_health():
    """Check Redis cache health."""
    health_ok = await check_redis_health()
    return {
        "redis_connected": health_ok,
        "status": "healthy" if health_ok else "unhealthy"
    }


@router.post("/cache/set", response_model=dict)
async def cache_set(request: CacheSetRequest):
    """Set a value in cache."""
    result = await cache.set(request.key, request.value, ttl=request.ttl)
    return {
        "success": result,
        "key": request.key,
        "message": "Value cached" if result else "Failed to cache"
    }


@router.get("/cache/get/{key}", response_model=CacheGetResponse)
async def cache_get(key: str):
    """Get a value from cache."""
    value = await cache.get(key)
    exists = await cache.exists(key)
    return CacheGetResponse(
        key=key,
        value=value,
        exists=exists
    )


@router.delete("/cache/delete/{key}")
async def cache_delete(key: str):
    """Delete a key from cache."""
    deleted = await cache.delete(key)
    return {
        "success": deleted,
        "key": key,
        "message": "Key deleted" if deleted else "Key not found"
    }



@router.get("/cache/exists/{key}")
async def cache_exists(key: str):
    """Check if a key exists in cache."""
    exists = await cache.exists(key)
    return {
        "key": key,
        "exists": exists
    }


@router.get("/cache/keys")
async def cache_list_keys(pattern: str | None = None):
    """
    List all cached keys with TTL, optionally filtered by pattern.

    Args:
        pattern: Optional pattern to match (e.g., "poll:*").
                If not provided, returns all keys.

    Returns:
        Dictionary with list of keys (with TTL) and count
    """
    keys = await cache.list_keys(pattern=pattern)

    # Get TTL for each key
    keys_with_ttl = []
    for key in keys:
        ttl = await cache.get_ttl(key)
        keys_with_ttl.append({
            "key": key,
            "ttl": ttl  # TTL in seconds, None if key doesn't exist or has no TTL
        })

    return {
        "keys": keys_with_ttl,
        "count": len(keys),
        "pattern": pattern if pattern else "*"
    }


@router.delete("/cache/clear")
async def cache_clear_all():
    """
    Delete all cache keys and associated data.

    WARNING: This is a destructive operation that will permanently delete
    all cached data. Use with caution.

    Returns:
        Dictionary with number of keys deleted
    """
    deleted_count = await cache.clear_all()
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} cache keys"
    }
