"""
Modbus TCP Client Module

Handles all Modbus TCP communication logic, connection management,
and error translation. Separated from the FastAPI application layer.
"""

from contextlib import contextmanager

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

from config import settings
from helpers.modbus import translate_modbus_error

__all__ = ["ModbusClient"]


@contextmanager
def modbus_client(host: str | None = None, port: int | None = None):
    """
    Context manager for Modbus TCP client connections.
    Ensures proper cleanup of sockets after use.

    Args:
        host: Modbus server hostname or IP (defaults to settings.modbus_host)
        port: Modbus server port (defaults to settings.modbus_port)
    """
    client = ModbusTcpClient(
        host=host or settings.modbus_host,
        port=port or settings.modbus_port,
        timeout=settings.modbus_timeout_s,
        retries=settings.modbus_retries,
    )
    try:
        yield client
    finally:
        client.close()


class ModbusClient:
    """Wrapper class for Modbus TCP operations."""

    def read_registers(
        self,
        kind: str,
        address: int,
        count: int,
        server_id: int,
        host: str,
        port: int,
    ) -> list[int | bool]:
        """
        Read Modbus registers or coils/discrete inputs.

        Args:
            kind: Type of register to read (holding, input, coils, discretes)
            address: Starting address
            count: Number of registers/bits to read
            server_id: Modbus unit/slave ID
            host: Modbus server hostname or IP address
            port: Modbus server port

        Returns:
            List of register values or bits

        Raises:
            Exception: Various Modbus exceptions that should be translated
        """
        with modbus_client(host=host, port=port) as client:
            if not client.connect():
                raise ConnectionException("Failed to connect to Modbus server")

            if kind == "holding":
                result = client.read_holding_registers(address=address, count=count, device_id=server_id)
                if result.isError():
                    raise ModbusException(str(result))
                return result.registers

            elif kind == "input":
                result = client.read_input_registers(address=address, count=count, device_id=server_id)
                if result.isError():
                    raise ModbusException(str(result))
                return result.registers

            elif kind == "coils":
                result = client.read_coils(address=address, count=count, device_id=server_id)
                if result.isError():
                    raise ModbusException(str(result))
                return result.bits

            else:
                raise ValueError(f"Invalid kind: {kind}")

    def modbus_server_health_check(self) -> tuple[bool, str]:
        """
        Perform a health check by connecting and reading a single holding register.

        Returns:
            Tuple of (success: bool, detail: str)
        """
        try:
            with modbus_client() as client:
                if not client.connect():
                    return False, "Failed to establish connection"

                result = client.read_holding_registers(
                    address=0,
                    count=1,
                    device_id=settings.modbus_device_id,
                )

                if result.isError():
                    return False, f"Read test failed: {result}"

                return True, "Connection and read test successful"

        except Exception as e:
            _, message = translate_modbus_error(e)
            return False, message
