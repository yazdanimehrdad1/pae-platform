"""APScheduler engine initialization and lifecycle management."""

import time
from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from logger import get_logger
from scheduler.jobs import cron_job_poll_modbus_registers_all_sites
from scheduler.locks import lock_manager

logger = get_logger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


async def start_scheduler() -> None:
    """
    Initialize and start the APScheduler.

    Only starts if scheduler is enabled and Redis is available.
    """
    # Initialize the scheduler
    global _scheduler

    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled")
        return

    try:
        from cache.connection import check_redis_health

        # Check Redis availability
        if not await check_redis_health():
            logger.warning("Redis unavailable, scheduler will not start")
            return

        # Initialize scheduler
        _scheduler = AsyncIOScheduler()

        # Start scheduler
        _scheduler.start()
        logger.info("APScheduler started")

        # Start leader election heartbeat
        await lock_manager.start_heartbeat()

        # Attempt initial leader acquisition
        await lock_manager.acquire_leader_lock()

        # Register scheduled jobs
        register_jobs()

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        _scheduler = None


async def stop_scheduler() -> None:
    """
    Stop the APScheduler and cleanup resources.
    """
    global _scheduler

    if _scheduler is None:
        return

    try:
        # Stop heartbeat
        await lock_manager.stop_heartbeat()

        # Release leader lock
        await lock_manager.release_leader_lock()

        # Shutdown scheduler
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("APScheduler stopped")

    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}", exc_info=True)


def _wrap_job_with_locks(job_func: Callable, job_id: str) -> Callable:
    """
    Wrap a job function with leader and per-job lock checks.

    Returns a callable that APScheduler can invoke.

    Args:
        job_func: Original job function (async)
        job_id: Job identifier

    Returns:
        Async function that wraps the original with lock checks
    """
    async def wrapped_job():
        """Wrapped job with lock verification."""
        # Check if we're the leader
        if not await lock_manager.is_leader():
            logger.debug(f"Skipping job {job_id} - not the leader")
            return

        # Check Redis connectivity
        from cache.connection import check_redis_health
        if not await check_redis_health():
            logger.warning(f"Skipping job {job_id} - Redis unavailable")
            return

        # Acquire per-job lock
        execution_timestamp = int(time.time())
        if not await lock_manager.acquire_job_lock(job_id, execution_timestamp):
            logger.warning(f"Skipping job {job_id} - per-job lock acquisition failed")
            return

        # Execute job
        try:
            logger.info(f"Executing scheduled job: {job_id} (pod: {lock_manager.pod_id})")
            await job_func()
        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}", exc_info=True)

    return wrapped_job


def add_job(
    job_func: Callable,
    trigger: Any,
    job_id: str,
    name: str | None = None,
    **kwargs
) -> None:
    """
    Add a job to the scheduler with automatic lock wrapping.

    Args:
        job_func: Async function to execute
        trigger: APScheduler trigger (e.g., IntervalTrigger, CronTrigger)
        job_id: Unique job identifier
        name: Human-readable job name (defaults to job_id)
        **kwargs: Additional job parameters
    """
    if _scheduler is None:
        logger.warning(f"Cannot add job {job_id}: scheduler not initialized")
        return

    # Wrap job function with lock checks
    wrapped_job = _wrap_job_with_locks(job_func, job_id)

    _scheduler.add_job(
        wrapped_job,
        trigger=trigger,
        id=job_id,
        name=name or job_id,
        replace_existing=True,
        **kwargs
    )
    logger.info(f"Registered scheduled job: {job_id} ({name or job_id})")


def register_jobs() -> None:
    """
    Register all scheduled jobs with the scheduler.

    This function should be called after the scheduler is started.
    Each job registration is handled by a separate function for clarity.
    """
    if _scheduler is None:
        logger.warning("Cannot register jobs: scheduler not initialized")
        return

    # Register all cron jobs
    _register_modbus_polling_job()

    logger.info("All scheduled jobs registered")


def _register_modbus_polling_job() -> None:
    """
    Register the Modbus polling cron job.

    Polls Modbus registers at configured interval and stores data in Redis cache.
    """
    add_job(
        job_func=cron_job_poll_modbus_registers_all_sites,
        trigger=IntervalTrigger(seconds=settings.poll_interval_seconds),
        job_id="modbus_poll",
        name="Modbus Register Polling"
    )
