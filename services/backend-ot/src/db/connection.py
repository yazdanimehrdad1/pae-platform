"""
PostgreSQL/TimescaleDB connection management.

Handles database connection creation, connection pooling, and lifecycle management.
Supports both asyncpg (legacy) and SQLAlchemy 2.0+ async (new) connections.
"""

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings
from logger import get_logger

logger = get_logger(__name__)

# ============================================================================
# Legacy asyncpg connection pool (for backward compatibility during migration)
# ============================================================================

# Global database connection pool (asyncpg - legacy)
_db_pool: asyncpg.Pool | None = None

# ============================================================================
# SQLAlchemy 2.0+ async engine and session (new)
# ============================================================================

# SQLAlchemy async engine
_async_engine: AsyncEngine | None = None

# SQLAlchemy async session factory
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_db_pool() -> asyncpg.Pool:
    """
    Get or create database connection pool.

    Uses connection pooling for efficient resource management.

    Returns:
        PostgreSQL async connection pool

    Raises:
        asyncpg.PostgresConnectionError: If unable to connect to database
    """
    global _db_pool

    if _db_pool is None:
        logger.info(
            f"Connecting to PostgreSQL at {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )

        try:
            _db_pool = await asyncpg.create_pool(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                min_size=1,
                max_size=settings.database_pool_size,
            )

            # Test connection
            async with _db_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.info("Successfully connected to PostgreSQL")

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    return _db_pool


async def close_db_pool() -> None:
    """
    Close database connection pool (legacy asyncpg).

    Should be called during application shutdown.
    """
    global _db_pool

    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("PostgreSQL connection pool (asyncpg) closed")


async def close_all_db_connections() -> None:
    """
    Close all database connections (both asyncpg and SQLAlchemy).

    Should be called during application shutdown.
    """
    await close_db_pool()  # Close legacy asyncpg pool
    await close_async_engine()  # Close SQLAlchemy engine


async def check_db_health() -> bool:
    """
    Check if database connection is healthy.

    Uses SQLAlchemy engine if available, falls back to asyncpg pool.

    Returns:
        True if database is accessible, False otherwise
    """
    try:
        # Try SQLAlchemy engine first (new approach)
        if _async_engine is not None:
            async with _async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        # Fallback to asyncpg pool (legacy)
        else:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False


# ============================================================================
# SQLAlchemy 2.0+ async engine and session management
# ============================================================================

def get_async_engine() -> AsyncEngine:
    """
    Get or create SQLAlchemy async engine.

    Creates a new async engine with connection pooling if it doesn't exist.
    Uses asyncpg as the database driver.

    Returns:
        SQLAlchemy async engine

    Raises:
        Exception: If unable to create engine
    """
    global _async_engine

    if _async_engine is None:
        # Build async database URL (using asyncpg driver)
        # Format: postgresql+asyncpg://user:password@host:port/dbname
        database_url = settings.database_url.replace(
            "postgresql://",
            "postgresql+asyncpg://"
        )

        logger.info(
            f"Creating SQLAlchemy async engine for PostgreSQL at "
            f"{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )

        try:
            _async_engine = create_async_engine(
                database_url,
                # Connection pool settings
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,   # Recycle connections after 1 hour
                echo=False,  # Set to True for SQL query logging (debug only)
            )

            logger.info("SQLAlchemy async engine created successfully")

        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy async engine: {e}")
            raise

    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create SQLAlchemy async session factory.

    Creates a session factory that generates async database sessions.
    Sessions are scoped to the current async context.

    Returns:
        SQLAlchemy async session factory
    """
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_async_engine()

        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit (better for async)
            autoflush=False,  # Don't autoflush (explicit control)
            autocommit=False,  # Use transactions explicitly
        )

        logger.info("SQLAlchemy async session factory created")

    return _async_session_factory


async def close_async_engine() -> None:
    """
    Close SQLAlchemy async engine and cleanup resources.

    Should be called during application shutdown.
    """
    global _async_engine, _async_session_factory

    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
        logger.info("SQLAlchemy async engine closed")

