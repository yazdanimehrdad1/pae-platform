"""Polling helpers for Modbus data collection."""

import asyncio
from datetime import UTC, datetime

from config import settings
from constants import MODBUS_MAX_REGISTERS_PER_READ
from helpers.device_points import get_device_points
from helpers.modbus import translate_modbus_error
from helpers.modbus.modbus_data_mapping import map_modbus_data_to_device_points
from helpers.modbus.store_data_readings import DbStoreResult, store_device_data_in_db
from helpers.sites import get_complete_site_data_with_points
from helpers.workers.device_poll import get_enabled_devices_to_poll, read_device_registers
from logger import get_logger
from schemas.api_models import DeviceListItem, DeviceWithPoints, PollingConfig, PollResult
from schemas.internal_models import DevicePollResult, FailedScanRange, RegisterMap

logger = get_logger(__name__)


async def poll_modbus_registers_per_site(site_id: int) -> None:
    """
    Scheduled job to poll Modbus registers for all enabled devices.

    1. Loads all devices for the site (with their scan_ranges and device points).
    2. For each poll-enabled device: reads scan ranges, maps register data to points, stores.
    3. Errors are isolated per device so one failure doesn't stop others.
    """
    logger.info("Starting Modbus polling job")

    try:
        complete_site_data = await get_complete_site_data_with_points(site_id)
        if complete_site_data is None:
            logger.warning(f"Site with id {site_id} not found")
            return

        site_name = complete_site_data.name
        devices_list = complete_site_data.devices

        if not devices_list:
            logger.warning(f"No devices for site with id {site_id}")
            return

        enabled_devices_to_poll = await get_enabled_devices_to_poll(devices_list, site_name)

        results: list[PollResult] = await asyncio.gather(
            *[poll_single_device_modbus(site_name, device) for device in enabled_devices_to_poll],
            return_exceptions=True
        )

        processed_results: list[PollResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                device_name = enabled_devices_to_poll[i].name if i < len(enabled_devices_to_poll) else "unknown"
                logger.error(f"Unexpected error polling device '{device_name}': {result}", exc_info=True)
                processed_results.append({
                    "device_name": device_name,
                    "success": False,
                    "cache_successful": 0,
                    "cache_failed": 0,
                    "db_successful": 0,
                    "db_failed": 0,
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        results = processed_results

        successful_devices = sum(1 for r in results if r.get("success", False))
        failed_devices = len(results) - successful_devices
        total_cache_successful = sum(r.get("cache_successful", 0) for r in results)
        total_cache_failed = sum(r.get("cache_failed", 0) for r in results)
        total_db_successful = sum(r.get("db_successful", 0) for r in results)
        total_db_failed = sum(r.get("db_failed", 0) for r in results)

        logger.info(
            f"Modbus polling job completed: "
            f"{successful_devices} device(s) successful, {failed_devices} device(s) failed | "
            f"Cache: {total_cache_successful} successful, {total_cache_failed} failed | "
            f"Database: {total_db_successful} successful, {total_db_failed} failed"
        )

        for result in results:
            if not result.get("success", False):
                logger.warning(
                    f"Device '{result.get('device_name', 'unknown')}' polling failed: "
                    f"{result.get('error', 'Unknown error')}"
                )

    except Exception as e:
        logger.error(f"Error in Modbus polling job: {e}", exc_info=True)


async def poll_single_device_modbus(site_name: str, device: DeviceWithPoints) -> PollResult:
    """
    Poll a single device using its scan_ranges.
    If scan_ranges is None the device is skipped (no ranges configured yet).
    """
    device_name = device.name
    result: PollResult = {
        "device_name": device_name,
        "success": False,
        "cache_successful": 0,
        "cache_failed": 0,
        "db_successful": 0,
        "db_failed": 0,
        "error": None
    }

    if device.scan_ranges is None:
        result["error"] = "No scan_ranges configured — set them via POST /device or PUT /scan-ranges"
        logger.warning(
            "site_name='%s', device_name='%s': no scan_ranges configured, skipping poll",
            site_name, device_name,
        )
        return result
    device = DeviceListItem(
        device_id=device.device_id,
        site_id=device.site_id,
        name=device.name,
        type=device.type,
        vendor=device.vendor,
        model=device.model,
        host=device.host,
        port=device.port,
        timeout=device.timeout,
        server_address=device.server_address,
        description=device.description,
        poll_enabled=device.poll_enabled,
        read_from_aggregator=device.read_from_aggregator,
        modbus_address_mode=device.modbus_address_mode,
        scan_ranges=device.scan_ranges,
        scan_ranges_locked=device.scan_ranges_locked,
        protocol=device.protocol,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )

    total_db_successful = 0
    total_db_failed = 0
    try:
        device_points_all = await get_device_points(device.device_id)
        timestamp_dt = datetime.now(UTC)

        scan_poll_result: DevicePollResult = await _poll_device_scan_ranges(
            device, site_name
        )
        if scan_poll_result.failed_ranges:
            logger.warning(
                "site_name='%s', device_name='%s': %d scan range(s) failed to poll",
                site_name, device_name, len(scan_poll_result.failed_ranges),
            )

        mapped_raw_registers_to_device_points_all = map_modbus_data_to_device_points(
            timestamp_dt=timestamp_dt,
            device_points_list=device_points_all,
            register_map=scan_poll_result.register_map,
            site_name=site_name,
            device_name=device_name,
        )

        if not mapped_raw_registers_to_device_points_all:
            result["error"] = "No device points configured — skipping DB store"
            logger.warning(
                f"site_name='{site_name}', device_name='{device_name}': "
                "no device points configured — skipping DB store"
            )
            return result

        # Check if any readings have a non-null derived_value
        has_any_reading = any(reading.derived_value is not None for reading in mapped_raw_registers_to_device_points_all)
        if not has_any_reading:
            result["error"] = "All readings null — complete poll failure"
            logger.warning(
                f"site_name='{site_name}', device_name='{device_name}': "
                "all readings are null (complete poll failure) — skipping DB store"
            )
            return result

        db_result: DbStoreResult = await store_device_data_in_db(
            device.device_id,
            device.site_id,
            mapped_raw_registers_to_device_points_all,
            timestamp_dt,
            device_name=device_name,
        )

        total_db_successful = db_result.successful
        total_db_failed = db_result.failed

        result["success"] = True
        result["db_successful"] = total_db_successful
        result["db_failed"] = total_db_failed

        logger.info(
            f"site_name='{site_name}', device_name='{device_name}': polling completed — "
            f"DB: {total_db_successful} stored, {total_db_failed} failed"
        )

    except Exception as e:
        error_host = settings.modbus_host if device.read_from_aggregator else device.host
        error_port = settings.modbus_port if device.read_from_aggregator else device.port
        status_code, error_message = translate_modbus_error(e, host=error_host, port=error_port)
        result["error"] = f"status_code={status_code}, error_message={error_message}"
        logger.error(
            f"site_name='{site_name}', device_name='{device_name}': polling error — {result['error']}",
            exc_info=True
        )

    return result


async def _poll_device_scan_ranges(
    device: DeviceListItem,
    site_name: str,
) -> DevicePollResult:
    """
    Poll using device.scan_ranges.
    Iterates holding/input/coils range lists, reads each block, merges into a RegisterMap.
    """
    merged: dict[int, int | bool] = {}
    failed_ranges: list[FailedScanRange] = []
    addr_offset = -1 if device.modbus_address_mode == "one_based" else 0

    for poll_kind, range_list in [
        ("holding", device.scan_ranges.holding),
        ("input", device.scan_ranges.input),
        ("coils", device.scan_ranges.coils),
    ]:
        for range_block in range_list:
            request_address = range_block.start_index + addr_offset
            polling_config = PollingConfig(
                poll_address=request_address,
                poll_count=range_block.count,
                poll_kind=poll_kind,
            )
            try:
                raw = await _read_scan_range_registers(device, polling_config, site_name=site_name)
                # Re-key the map back to configured addresses so point lookups match
                if addr_offset != 0:
                    merged.update({addr - addr_offset: val for addr, val in raw.values.items()})
                else:
                    merged.update(raw.values)
            except Exception as error:
                error_host = settings.modbus_host if device.read_from_aggregator else (device.host or "unknown")
                error_port = settings.modbus_port if device.read_from_aggregator else (device.port or "unknown")
                try:
                    status_code, error_message = translate_modbus_error(error, host=error_host, port=error_port)
                except Exception as translate_error:
                    status_code = 500
                    error_message = (
                        f"{type(error).__name__}: {error} "
                        f"(error translation also failed: {translate_error})"
                    )
                logger.warning(
                    "site_name='%s', device_name='%s', %s@%s count=%s failed: [%s] %s",
                    site_name, device.name, poll_kind, range_block.start_index,
                    range_block.count, status_code, error_message,
                )
                failed_ranges.append(FailedScanRange(
                    poll_kind=poll_kind,
                    start_index=range_block.start_index,
                    count=range_block.count,
                    status_code=status_code,
                    error_message=error_message,
                ))

    return DevicePollResult(register_map=RegisterMap(values=merged), failed_ranges=failed_ranges)


async def _read_scan_range_registers(
    device: DeviceListItem,
    polling_config: PollingConfig,
    site_name: str,
) -> RegisterMap:
    """Read Modbus registers in chunks and return a flat address→value map."""
    start_address = int(polling_config.poll_address)
    total_count = polling_config.poll_count

    if total_count <= MODBUS_MAX_REGISTERS_PER_READ:
        raw_values = await read_device_registers(device, polling_config, site_name=site_name)
        if not raw_values:
            return RegisterMap()
        return RegisterMap(values={start_address + i: value for i, value in enumerate(raw_values)})

    values: dict[int, int | bool] = {}
    chunk_offset = 0
    while chunk_offset < total_count:
        chunk_count = min(MODBUS_MAX_REGISTERS_PER_READ, total_count - chunk_offset)
        chunk_start = start_address + chunk_offset
        chunk_config = PollingConfig(
            poll_address=chunk_start,
            poll_count=chunk_count,
            poll_kind=polling_config.poll_kind,
        )
        chunk_data = await read_device_registers(device, chunk_config, site_name=site_name)
        if not chunk_data:
            logger.warning(
                "site_name='%s', device_name='%s': chunked read returned no data at address=%s count=%s — aborting",
                site_name, device.name, chunk_start, chunk_count,
            )
            return RegisterMap()
        values.update({chunk_start + i: value for i, value in enumerate(chunk_data)})
        chunk_offset += chunk_count

    return RegisterMap(values=values)
