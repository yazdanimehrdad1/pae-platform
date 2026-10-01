"""Scheduled jobs: Modbus polling, and alarm evaluation."""

from datetime import UTC, datetime

from db.sites import get_all_sites
from helpers.alarms.evaluation import evaluate_all_sites_alarms
from helpers.modbus.poll_device import poll_modbus_registers_per_site
from logger import get_logger

logger = get_logger(__name__)


async def cron_job_poll_modbus_registers_all_sites() -> None:
    """
    Scheduled job to poll Modbus registers for all sites.
    """
    logger.info("Starting Modbus polling job for all sites")
    try:
        #TODO: consider getting this from cache if possible to reduce database load
        all_sites = await get_all_sites()
        logger.info(f"Retrieved {len(all_sites)} site(s) from database")
        for site in all_sites:
            await poll_modbus_registers_per_site(site.site_id)
    except Exception as e:
        # Don't re-raise - let scheduler handle retry on next interval
        logger.error(f"Error in Modbus polling job for all sites: {e}", exc_info=True)


async def cron_job_evaluate_alarms_all_sites() -> None:
    """
    Scheduled job to evaluate every site's alarms from stored readings, recording raises and clears.
    """
    try:
        await evaluate_all_sites_alarms(datetime.now(UTC))
    except Exception as e:
        # Don't re-raise - let scheduler handle retry on next interval
        logger.error(f"Error in alarm evaluation job: {e}", exc_info=True)
