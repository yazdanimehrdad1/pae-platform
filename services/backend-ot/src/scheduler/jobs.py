"""Polling jobs for Modbus data collection."""

from db.sites import get_all_sites
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
