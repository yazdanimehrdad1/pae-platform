"""The Modbus server's register layout: /modbus/registers."""

from fastapi import APIRouter, Depends

from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import (
    ModbusDevice,
    ModbusRegister,
    ModbusRegistersResponse,
)
from powerflow.point_standard import build_layout
from powerflow.settings import settings

router = APIRouter(tags=["modbus"])


@router.get(
    "/modbus/registers",
    response_model=ModbusRegistersResponse,
    summary="Register layout of the Modbus server for the active site",
    description="One aggregator device (one port, one unit id); each device owns a "
    "100-register chunk. `powerflow_server` says whether a point is served (yes / calc) or "
    "always reads 0 (no).",
)
async def modbus_registers(
    context: AdapterContext = Depends(get_context),
) -> ModbusRegistersResponse:
    config = context.engine.config
    return ModbusRegistersResponse(
        enabled=config.interfaces.modbus.enabled,
        port=settings.modbus_port,
        unit_id=settings.modbus_unit_id,
        devices=[
            ModbusDevice(
                kind=device.kind,
                asset_id=device.asset_id,
                base=device.base,
                registers=[
                    ModbusRegister(
                        address=register.address,
                        point=register.row.point,
                        data_type=register.row.data_type,
                        scale=register.row.scale,
                        unit=register.row.unit,
                        powerflow_server=register.row.support,
                    )
                    for register in device.registers
                ],
            )
            for device in build_layout(config, context.point_standard)
        ],
    )
