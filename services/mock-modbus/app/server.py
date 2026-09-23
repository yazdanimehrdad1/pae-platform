from __future__ import annotations

import asyncio
import logging
import sys

from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer

from app.datastore import build_device_blocks
from app.modbus_mock_data import DEVICES
from app.models import DeviceSpec, DeviceType
from app.profiles import ProfileConfig
from app.settings import Settings
from app.timeseries_data.pv_profile_static import PV_PROFILE_STATIC

logger = logging.getLogger("mock_modbus")


def _build_profile_config(settings: Settings) -> ProfileConfig:
    """Profile knobs from Settings — the only place Settings crosses into it."""
    return ProfileConfig(
        timezone_offset_hours=settings.profile_timezone_offset_hours,
        day_minutes=settings.profile_day_minutes,
    )


def _static_profile_for(device: DeviceSpec):
    """The frozen table a device's type="profile_static" registers read from.

    Keyed by address, so a table only makes sense for the device whose register
    map it was written against. Only PV devices have one today; anything else
    gets None and will fail loudly at startup if it declares a static register.
    """
    if device.device_type is DeviceType.PV:
        return PV_PROFILE_STATIC
    return None


async def _start_aggregator(settings: Settings) -> None:
    """One TCP server, all devices registered by their unit_id."""
    device_contexts: dict[int, ModbusSlaveContext] = {}
    profile_config = _build_profile_config(settings)

    for device in DEVICES:
        holding_register_block, input_register_block = build_device_blocks(
            device.holding_registers,
            device.input_registers,
            default_value=settings.default_register_value,
            seed=settings.random_seed,
            profile_config=profile_config,
            static_profile=_static_profile_for(device),
        )
        device_contexts[device.unit_id] = ModbusSlaveContext(hr=holding_register_block, ir=input_register_block, zero_mode=settings.zero_mode)
        logger.info("  Registered %-12s unit_id=%d", device.name, device.unit_id)

    context = ModbusServerContext(slaves=device_contexts, single=False)

    logger.info(
        "Starting aggregator server on %s:%d (%d device(s))",
        settings.modbus_host,
        settings.modbus_port,
        len(DEVICES),
    )
    await StartAsyncTcpServer(
        context=context,
        address=(settings.modbus_host, settings.modbus_port),
    )


async def _start_per_device(settings: Settings) -> None:
    """One TCP server per device, each on its own host/port."""
    servers = []
    profile_config = _build_profile_config(settings)

    for device in DEVICES:
        holding_register_block, input_register_block = build_device_blocks(
            device.holding_registers,
            device.input_registers,
            default_value=settings.default_register_value,
            seed=settings.random_seed,
            profile_config=profile_config,
            static_profile=_static_profile_for(device),
        )
        context = ModbusServerContext(
            slaves={device.unit_id: ModbusSlaveContext(hr=holding_register_block, ir=input_register_block, zero_mode=settings.zero_mode)},
            single=False,
        )
        logger.info(
            "  Starting %-12s on %s:%d  unit_id=%d",
            device.name,
            device.host,
            device.port,
            device.unit_id,
        )
        servers.append(
            StartAsyncTcpServer(context=context, address=(device.host, device.port))
        )

    await asyncio.gather(*servers)


async def run_server() -> None:
    settings = Settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    logger.info("Configuration:")
    logger.info("  aggregator_enabled  = %s", settings.aggregator_enabled)
    logger.info("  per_device_enabled  = %s", settings.per_device_enabled)
    logger.info("  devices             = %d", len(DEVICES))
    logger.info("  default_value       = %d", settings.default_register_value)
    logger.info("  random_seed         = %s", settings.random_seed)
    logger.info("  zero_mode           = %s", settings.zero_mode)
    logger.info("  profile_tz_offset_h = %s", settings.profile_timezone_offset_hours)
    logger.info("  profile_day_minutes = %s", settings.profile_day_minutes)

    servers = []

    if settings.aggregator_enabled:
        logger.info("  aggregator host     = %s:%d", settings.modbus_host, settings.modbus_port)
        servers.append(_start_aggregator(settings))

    if settings.per_device_enabled:
        servers.append(_start_per_device(settings))

    if not servers:
        logger.error("Nothing to start: set AGGREGATOR_ENABLED and/or PER_DEVICE_ENABLED.")
        sys.exit(1)

    await asyncio.gather(*servers)


if __name__ == "__main__":
    asyncio.run(run_server())
