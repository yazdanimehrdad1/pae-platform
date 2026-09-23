"""
SQLAlchemy async session management utilities.

Provides helper functions for working with async database sessions.
"""

from contextlib import AbstractAsyncContextManager, asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_async_session_factory
from logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def get_session() -> AbstractAsyncContextManager[AsyncSession]:
    """
    Get async database session.

    Usage:
        async with get_session() as session:
            # Use session here
            result = await session.execute(select(Model))
            ...

    Yields:
        AsyncSession: Database session
    """
    factory = get_async_session_factory()

    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
