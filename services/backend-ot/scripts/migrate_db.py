#!/usr/bin/env python3
"""
Database migration utility script.

Runs all migration files in order from src/db/migrations/ directory.
Tracks applied migrations in schema_migrations table.

Usage:
    python scripts/migrate_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db.connection import get_db_pool, close_db_pool
from logger import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


async def ensure_migrations_table(pool):
    """Create schema_migrations table if it doesn't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        logger.debug("Schema migrations table ensured")


async def get_applied_migrations(pool):
    """Get list of already applied migration versions."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        return {row['version'] for row in rows}


async def run_migration(pool, migration_file: Path):
    """Run a single migration file."""
    version = migration_file.stem  # e.g., "001_create_devices_table" 
    
    logger.info(f"Running migration: {migration_file.name}")
    
    sql = migration_file.read_text()
    
    async with pool.acquire() as conn:
        # Run migration in a transaction
        async with conn.transaction():
            await conn.execute(sql)
            
            # Record migration as applied
            await conn.execute("""
                INSERT INTO schema_migrations (version) 
                VALUES ($1)
                ON CONFLICT (version) DO NOTHING
            """, version)
    
    logger.info(f"✓ Migration {version} completed")


async def run_all_migrations():
    """Run all pending migrations in order."""
    try:
        logger.info("Starting database migrations...")
        
        # Get database pool
        pool = await get_db_pool()
        
        # Ensure migrations table exists
        await ensure_migrations_table(pool)
        
        # Get migrations directory
        migrations_dir = Path(__file__).parent.parent / "src" / "db" / "migrations"
        
        if not migrations_dir.exists():
            logger.error(f"Migrations directory not found: {migrations_dir}")
            return False
        
        # Get all SQL migration files, sorted by name
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        if not migration_files:
            logger.warning("No migration files found")
            return True
        
        logger.info(f"Found {len(migration_files)} migration file(s)")
        
        # Get already applied migrations
        applied = await get_applied_migrations(pool)
        logger.info(f"Found {len(applied)} already applied migration(s)")
        
        # Run pending migrations
        pending_count = 0
        for migration_file in migration_files:
            version = migration_file.stem
            
            if version in applied:
                logger.info(f"⏭ Skipping {migration_file.name} (already applied)")
                continue
            
            await run_migration(pool, migration_file)
            pending_count += 1
        
        if pending_count == 0:
            logger.info("✓ All migrations are up to date")
        else:
            logger.info(f"✓ Applied {pending_count} new migration(s)")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}", exc_info=True)
        return False
    finally:
        await close_db_pool()


if __name__ == "__main__":
    success = asyncio.run(run_all_migrations())
    sys.exit(0 if success else 1)

