"""Modbus TCP adapter: the simulated site as one aggregator device (one port, one unit id).

The register layout and every value come from `powerflow.point_standard`. This module only
serves them:

- A background task watches for new snapshots. On each new step it rebuilds the register image
  (energy counters come with the snapshot); when the active site changes, it rebuilds the layout
  too.
- pymodbus serves a single shared register block, so FC03 (holding) and FC04 (input) read the
  same values. The device's `action` hook copies the current image into the block on every read.
- Read-only: writes are answered with ILLEGAL_FUNCTION. Setpoints stay on HTTP for now.
"""

import asyncio
import logging
from contextlib import suppress

from pymodbus.constants import ExcCodes
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from powerflow.interfaces.base import AdapterContext, ProtocolAdapter
from powerflow.point_standard import (
    REGISTER_SPACE,
    Device,
    build_image,
    build_layout,
)
from powerflow.point_standard.sources import sources_from
from powerflow.site_config import SiteConfig

logger = logging.getLogger(__name__)
REFRESH_INTERVAL_S = 0.25


class ModbusAdapter(ProtocolAdapter):
    name = "modbus"

    def __init__(self, context: AdapterContext, host: str, port: int, unit_id: int) -> None:
        self._context = context
        self._address = (host, port)
        self._unit_id = unit_id
        self._config: SiteConfig | None = None
        self._devices: tuple[Device, ...] = ()
        self._step_id: int | None = None
        self._image: dict[int, int] = {}
        self._server: ModbusTcpServer | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def port(self) -> int:
        """The bound port (useful when started on port 0)."""
        # A listening pymodbus server's transport is the asyncio.Server it created.
        listener = self._server.transport if self._server is not None else None
        if not isinstance(listener, asyncio.Server) or not listener.sockets:
            return self._address[1]
        return int(listener.sockets[0].getsockname()[1])

    async def start(self) -> None:
        self.refresh()
        device = SimDevice(
            self._unit_id,
            simdata=[SimData(0, count=REGISTER_SPACE, values=0, datatype=DataType.REGISTERS)],
            action=self._on_request,
        )
        self._server = ModbusTcpServer(device, address=self._address)
        try:
            await self._server.serve_forever(background=True)
        except RuntimeError as error:  # pymodbus: "Could not start listen" (port taken, ...)
            raise OSError(
                f"Modbus can't listen on {self._address[0]}:{self._address[1]}"
            ) from error
        self._task = asyncio.create_task(self._refresh_loop())
        logger.info(
            "modbus: serving %d devices on %s:%d unit %d",
            len(self._devices),
            self._address[0],
            self.port,
            self._unit_id,
        )

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        if self._server is not None:
            await self._server.shutdown()

    def refresh(self) -> None:
        """Bring the layout and the register image up to date with the engine."""
        engine = self._context.engine
        if engine.config is not self._config:
            self._config = engine.config
            self._devices = build_layout(engine.config, self._context.point_standard)
            self._step_id = None
        latest = engine.store.latest
        if latest is None:
            self._image, self._step_id = {}, None
            return
        if latest.step_id == self._step_id:
            return
        sources = sources_from(
            latest, engine.config, self._context.points, self._context.point_standard.enums
        )
        self._image = build_image(self._devices, sources)
        self._step_id = latest.step_id

    async def _refresh_loop(self) -> None:
        while True:
            try:
                self.refresh()
            except Exception:  # keep serving the last image; the next tick retries
                logger.exception("modbus: register refresh failed")
            await asyncio.sleep(REFRESH_INTERVAL_S)

    async def _on_request(
        self,
        _function_code: int,
        start_address: int,
        address: int,
        count: int,
        registers: list[int],
        set_values: list[int] | list[bool] | None,
    ) -> ExcCodes | None:
        if set_values is not None:
            logger.warning("modbus: write to %d refused (read-only server)", address)
            return ExcCodes.ILLEGAL_FUNCTION
        for offset in range(count):
            registers[address - start_address + offset] = self._image.get(address + offset, 0)
        return None
