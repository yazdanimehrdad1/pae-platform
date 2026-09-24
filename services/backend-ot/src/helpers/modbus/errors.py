"""
Modbus helper functions.

Contains shared Modbus error translation logic for API and jobs.
"""

from pymodbus.exceptions import ConnectionException, ModbusException

from config import settings


def translate_modbus_error(
    error: Exception,
    host: str | None = None,
    port: int | None = None
) -> tuple[int, str]:
    """
    Translate Modbus exceptions into appropriate HTTP status codes and messages.
    """
    if isinstance(error, ConnectionException):
        error_host = host or settings.modbus_host
        error_port = port or settings.modbus_port
        return (
            503,
            f"Failed to connect to Modbus server at {error_host}:{error_port}"
        )
    if isinstance(error, ModbusException):
        return (
            400,
            f"Modbus error: {str(error)}"
        )
    if isinstance(error, TimeoutError):
        return (
            504,
            f"Request timed out after {settings.modbus_timeout_s}s"
        )
    return (
        500,
        f"Unexpected error: {str(error)}"
    )
