"""
Redis connection management.

Handles Redis client creation, connection pooling, and lifecycle management.
"""


import redis.asyncio as aioredis

from config import settings
from logger import get_logger

logger = get_logger(__name__)

# Global Redis client instance
_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis:
    """
    Get or create Redis client connection.

    Uses connection pooling for efficient resource management.

    Returns:
        Redis async client instance

    Raises:
        redis.ConnectionError: If unable to connect to Redis
    """
    global _redis_client

    if _redis_client is None:
        logger.info(
            f"Connecting to Redis at {settings.redis_host}:{settings.redis_port}"
        )

        try:
            _redis_client = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                max_connections=settings.redis_max_connections,
                decode_responses=settings.redis_decode_responses,
                health_check_interval=settings.redis_health_check_interval,
            )

            # Test connection
            await _redis_client.ping()
            logger.info("Successfully connected to Redis")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    return _redis_client


async def close_redis_client() -> None:
    """
    Close Redis client connection and cleanup resources.

    Should be called during application shutdown.
    """
    global _redis_client

    if _redis_client is not None:
        logger.info("Closing Redis connection")
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


async def check_redis_health() -> bool:
    """
    Check if Redis connection is healthy.

    Returns:
        True if Redis is reachable, False otherwise
    """
    try:
        client = await get_redis_client()
        await client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False

