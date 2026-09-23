"""Persistent Modbus TCP connection for SSE streaming sessions."""

import asyncio
from typing import Literal

from pymodbus.client import ModbusTcpClient

from services.server_sent_events.errors import (
    LiveStreamRawRegistersConnectionError,
    LiveStreamRawRegistersReadError,
)


class LiveStreamRawRegistersConnection:
    """
    Wraps a single ModbusTcpClient for the duration of one SSE session.
    Call connect() once, read() repeatedly, then close() in a finally block.
    """

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self._client = ModbusTcpClient(host=host, port=port, timeout=timeout)
        self._host = host
        self._port = port

    async def connect(self) -> None:
        connected = await asyncio.to_thread(self._client.connect)
        if not connected:
            raise LiveStreamRawRegistersConnectionError(
                f"Failed to connect to {self._host}:{self._port}"
            )

    async def read(
        self,
        kind: Literal["holding", "input"],
        address: int,
        count: int,
        device_id: int,
    ) -> list[int]:
        if kind == "holding":
            fn = self._client.read_holding_registers
        else:
            fn = self._client.read_input_registers

        result = await asyncio.to_thread(
            fn,
            address=address,
            count=count,
            device_id=device_id,
        )

        if result.isError():
            raise LiveStreamRawRegistersReadError(str(result))

        return result.registers

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
