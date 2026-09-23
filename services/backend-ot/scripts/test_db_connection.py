#!/usr/bin/env python3
"""
Simple script to test PostgreSQL/TimescaleDB connection.

Usage:
    python scripts/test_db_connection.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db.connection import get_db_pool, check_db_health, close_db_pool
from logger import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


async def test_connection():
    """Test database connection."""
    try:
        logger.info("Testing database connection...")
        
        # Get connection pool
        pool = await get_db_pool()
        logger.info("✓ Connection pool created")
        
        # Test health check
        health_ok = await check_db_health()
        if health_ok:
            logger.info("✓ Database health check passed")
        else:
            logger.error("✗ Database health check failed")
            return False
        
        # Test a simple query
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT version()")
            logger.info(f"✓ PostgreSQL version: {result}")
            
            # Check if TimescaleDB extension is available
            timescale_version = await conn.fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
            )
            if timescale_version:
                logger.info(f"✓ TimescaleDB extension found (version: {timescale_version})")
            else:
                logger.warning("⚠ TimescaleDB extension not found (may need to be installed)")
        
        logger.info("✓ All connection tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}", exc_info=True)
        return False
    finally:
        await close_db_pool()


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)

