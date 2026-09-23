"""
Redis caching service.

Provides high-level caching operations with TTL support and key prefixing.
"""

import json
from typing import Any

from cache.connection import get_redis_client
from config import settings
from logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """
    Redis-based caching service.

    Provides methods for storing and retrieving cached data with TTL support.
    Automatically handles key prefixing and JSON serialization.
    """

    def __init__(self, key_prefix: str | None = None, default_ttl: int | None = None):
        """
        Initialize cache service.

        Args:
            key_prefix: Prefix for all cache keys (defaults to settings.cache_key_prefix)
            default_ttl: Default TTL in seconds (defaults to settings.cache_default_ttl)
        """
        self.key_prefix = key_prefix or settings.cache_key_prefix
        self.default_ttl = default_ttl or settings.cache_default_ttl

    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.key_prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            Cached value if found, None otherwise
        """
        try:
            client = await get_redis_client()
            full_key = self._make_key(key)
            value = await client.get(full_key)

            if value is None:
                return None

            # Try to deserialize JSON, fallback to raw string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        except Exception as e:
            logger.warning(f"Cache get failed for key '{key}': {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key (will be prefixed automatically)
            value: Value to cache (will be JSON serialized if not a string)
            ttl: Time to live in seconds (defaults to self.default_ttl)

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await get_redis_client()
            full_key = self._make_key(key)

            # Serialize value to JSON if not a string
            if isinstance(value, str):
                serialized_value = value
            else:
                serialized_value = json.dumps(value)

            ttl = ttl if ttl is not None else self.default_ttl

            await client.set(full_key, serialized_value, ex=ttl)
            return True

        except Exception as e:
            logger.warning(f"Cache set failed for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            True if deleted, False otherwise
        """
        try:
            client = await get_redis_client()
            full_key = self._make_key(key)
            result = await client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.warning(f"Cache delete failed for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            True if key exists, False otherwise
        """
        try:
            client = await get_redis_client()
            full_key = self._make_key(key)
            result = await client.exists(full_key)
            return result > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed for key '{key}': {e}")
            return False

    async def get_ttl(self, key: str) -> int | None:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            TTL in seconds, None if key doesn't exist or has no TTL
        """
        try:
            client = await get_redis_client()
            full_key = self._make_key(key)
            ttl = await client.ttl(full_key)
            return ttl if ttl >= 0 else None
        except Exception as e:
            logger.warning(f"Cache get_ttl failed for key '{key}': {e}")
            return None

    async def list_keys(self, pattern: str | None = None) -> list[str]:
        """
        List all cache keys, optionally filtered by pattern.

        Args:
            pattern: Optional pattern to match (e.g., "poll:*").
                    If None, returns all keys with the prefix.
                    Pattern should not include the key prefix.

        Returns:
            List of cache keys (without prefix)
        """
        try:
            client = await get_redis_client()
            keys = []

            # Build the full pattern with prefix
            if pattern:
                full_pattern = self._make_key(pattern)
            else:
                full_pattern = f"{self.key_prefix}:*"

            # Use scan_iter to avoid blocking on large key sets
            async for key in client.scan_iter(match=full_pattern):
                # Remove prefix from key before returning
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str.startswith(f"{self.key_prefix}:"):
                    # Remove prefix and return the original key
                    keys.append(key_str[len(f"{self.key_prefix}:"):])
                else:
                    keys.append(key_str)

            return sorted(keys)
        except Exception as e:
            logger.warning(f"Cache list_keys failed for pattern '{pattern}': {e}")
            return []

    async def clear_all(self) -> int:
        """
        Delete all cache keys with the configured prefix.

        WARNING: This is a destructive operation that will delete all cached data.

        Returns:
            Number of keys deleted
        """
        try:
            client = await get_redis_client()
            full_pattern = f"{self.key_prefix}:*"
            deleted = 0

            # Use scan_iter to avoid blocking on large key sets
            async for key in client.scan_iter(match=full_pattern):
                await client.delete(key)
                deleted += 1

            logger.info(f"Cleared {deleted} cache keys with prefix '{self.key_prefix}'")
            return deleted
        except Exception as e:
            logger.error(f"Cache clear_all failed: {e}", exc_info=True)
            return 0


# Global cache service instance
cache = CacheService()

