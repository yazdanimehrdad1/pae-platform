"""
Redis-based distributed locking for scheduler leader election and job execution.
"""

import asyncio
import os

from cache.connection import check_redis_health, get_redis_client
from config import settings
from logger import get_logger

logger = get_logger(__name__)

# Leader lock key
LEADER_LOCK_KEY = "scheduler:leader"
JOB_LOCK_PREFIX = "scheduler:job"


def get_pod_identifier() -> str:
    """
    Get unique pod identifier for leader election.

    Uses POD_NAME env var if set, otherwise falls back to HOSTNAME.
    """
    pod_name = settings.pod_name or os.getenv("HOSTNAME", "unknown")
    return pod_name


class SchedulerLockManager:
    """
    Manages distributed locks for scheduler leader election and job execution.
    """

    def __init__(self):
        self.pod_id = get_pod_identifier()
        self._is_leader = False
        self._heartbeat_task: asyncio.Task | None = None

    async def acquire_leader_lock(self) -> bool:
        """
        Attempt to acquire the leader lock.

        Returns:
            True if lock acquired, False otherwise
        """
        try:
            redis_client = await get_redis_client()

            # Use SET NX EX for atomic lock acquisition
            result = await redis_client.set(
                LEADER_LOCK_KEY,
                self.pod_id,
                nx=True,  # Only set if not exists
                ex=settings.scheduler_leader_lock_ttl  # Expiration in seconds
            )

            if result:
                self._is_leader = True
                logger.info(f"Acquired scheduler leadership (pod: {self.pod_id})")
                return True
            else:
                # Check if we're already the leader (lock exists with our ID)
                current_leader = await redis_client.get(LEADER_LOCK_KEY)
                if current_leader == self.pod_id:
                    self._is_leader = True
                    logger.debug(f"Already leader (pod: {self.pod_id})")
                    return True
                else:
                    self._is_leader = False
                    logger.debug(f"Failed to acquire leadership - current leader: {current_leader}")
                    return False

        except Exception as e:
            logger.error(f"Error acquiring leader lock: {e}")
            self._is_leader = False
            return False

    async def renew_leader_lock(self) -> bool:
        """
        Renew the leader lock TTL if we're still the leader.

        Returns:
            True if renewal successful, False otherwise
        """
        try:
            redis_client = await get_redis_client()

            # Verify we still own the lock before renewing
            current_leader = await redis_client.get(LEADER_LOCK_KEY)
            if current_leader != self.pod_id:
                self._is_leader = False
                logger.warning(f"Lost leadership - current leader: {current_leader}")
                return False

            # Renew the lock TTL
            result = await redis_client.expire(
                LEADER_LOCK_KEY,
                settings.scheduler_leader_lock_ttl
            )

            if result:
                logger.debug(f"Renewed scheduler leadership (pod: {self.pod_id})")
                return True
            else:
                # Lock doesn't exist anymore
                self._is_leader = False
                logger.warning("Leader lock expired, attempting reacquisition")
                return False

        except Exception as e:
            logger.error(f"Error renewing leader lock: {e}")
            self._is_leader = False
            return False

    async def is_leader(self) -> bool:
        """
        Check if this pod is currently the leader.

        Returns:
            True if we're the leader, False otherwise
        """
        if not self._is_leader:
            return False

        try:
            redis_client = await get_redis_client()
            current_leader = await redis_client.get(LEADER_LOCK_KEY)

            if current_leader == self.pod_id:
                return True
            else:
                self._is_leader = False
                return False

        except Exception as e:
            logger.warning(f"Error checking leader status: {e}")
            self._is_leader = False
            return False

    async def release_leader_lock(self) -> None:
        """
        Release the leader lock (called on shutdown).
        """
        try:
            redis_client = await get_redis_client()
            current_leader = await redis_client.get(LEADER_LOCK_KEY)

            if current_leader == self.pod_id:
                await redis_client.delete(LEADER_LOCK_KEY)
                logger.info(f"Released scheduler leadership (pod: {self.pod_id})")

            self._is_leader = False

        except Exception as e:
            logger.error(f"Error releasing leader lock: {e}")

    async def acquire_job_lock(self, job_id: str, execution_timestamp: int) -> bool:
        """
        Acquire a per-job execution lock.

        Args:
            job_id: Unique job identifier
            execution_timestamp: Timestamp of this execution

        Returns:
            True if lock acquired, False otherwise
        """
        try:
            redis_client = await get_redis_client()
            job_lock_key = f"{JOB_LOCK_PREFIX}:{job_id}:{execution_timestamp}"

            # Use SET NX EX for atomic lock acquisition
            result = await redis_client.set(
                job_lock_key,
                self.pod_id,
                nx=True,
                ex=settings.scheduler_job_lock_ttl
            )

            if result:
                logger.debug(f"Acquired job lock: {job_lock_key}")
                return True
            else:
                logger.debug(f"Failed to acquire job lock: {job_lock_key} (already executing)")
                return False

        except Exception as e:
            logger.error(f"Error acquiring job lock: {e}")
            return False

    async def start_heartbeat(self) -> None:
        """
        Start the heartbeat task to renew leader lock periodically.
        """
        if self._heartbeat_task and not self._heartbeat_task.done():
            logger.warning("Heartbeat task already running")
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Started scheduler heartbeat task")

    async def stop_heartbeat(self) -> None:
        """
        Stop the heartbeat task.
        """
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped scheduler heartbeat task")

    async def _heartbeat_loop(self) -> None:
        """
        Background task that renews leader lock periodically.
        """
        while True:
            try:
                await asyncio.sleep(settings.scheduler_heartbeat_interval)

                if not await check_redis_health():
                    logger.warning("Redis unavailable, stopping heartbeat")
                    self._is_leader = False
                    # Wait and retry
                    await asyncio.sleep(settings.scheduler_leader_retry_interval)
                    continue

                if self._is_leader:
                    renewed = await self.renew_leader_lock()
                    if not renewed:
                        # Lost leadership, try to reacquire
                        logger.info("Attempting to reacquire leadership")
                        await self.acquire_leader_lock()
                else:
                    # Not leader, try to acquire
                    await self.acquire_leader_lock()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(settings.scheduler_heartbeat_interval)


# Global lock manager instance
lock_manager = SchedulerLockManager()

