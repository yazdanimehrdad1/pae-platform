"""Raw Modbus TCP client helpers for the tests.

Plain sockets and struct, deliberately not a pymodbus client: the tests then check the
bytes a real device client would see, independent of pymodbus's own client/server
pairing (and of its version).
"""

from __future__ import annotations

import socket
import struct

READ_HOLDING_REGISTERS = 0x03
READ_INPUT_REGISTERS = 0x04
WRITE_SINGLE_REGISTER = 0x06

_EXCEPTION_NAMES = {
    1: "ILLEGAL FUNCTION",
    2: "ILLEGAL DATA ADDRESS",
    3: "ILLEGAL DATA VALUE",
    4: "SERVER DEVICE FAILURE",
}


class ModbusExceptionResponse(Exception):
    """The server answered with a Modbus exception PDU (function code | 0x80)."""


def _mbap(transaction_id: int, unit_id: int, pdu: bytes) -> bytes:
    # MBAP header: transaction id, protocol id (0), length (unit id byte + PDU), unit id.
    return struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, unit_id) + pdu


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("server closed the connection mid-response")
        data += chunk
    return data


def _recv_response(sock: socket.socket) -> bytes:
    """One full response frame: the MBAP header says how many bytes follow it."""
    header = _recv_exact(sock, 7)
    _transaction_id, _protocol_id, length, _unit_id = struct.unpack(">HHHB", header)
    return header + _recv_exact(sock, length - 1)


class ModbusTcpClient:
    """Minimal synchronous Modbus TCP client over one socket."""

    def __init__(self, host: str, port: int, timeout_s: float = 5.0) -> None:
        self._sock = socket.create_connection((host, port), timeout=timeout_s)
        self._transaction_id = 0

    def close(self) -> None:
        self._sock.close()

    def __enter__(self) -> ModbusTcpClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, unit_id: int, pdu: bytes) -> bytes:
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        self._sock.sendall(_mbap(self._transaction_id, unit_id, pdu))
        response = _recv_response(self._sock)
        function_code = response[7]
        if function_code & 0x80:
            code = response[8]
            raise ModbusExceptionResponse(_EXCEPTION_NAMES.get(code, f"UNKNOWN ({code})"))
        return response

    def read_registers(
        self, function_code: int, wire_address: int, count: int, unit_id: int
    ) -> list[int]:
        """Read ``count`` uint16 registers starting at the on-the-wire (PDU) address."""
        response = self._request(unit_id, struct.pack(">BHH", function_code, wire_address, count))
        byte_count = response[8]
        payload = response[9 : 9 + byte_count]
        return [value for (value,) in struct.iter_unpack(">H", payload)]

    def write_register(self, wire_address: int, value: int, unit_id: int) -> None:
        self._request(unit_id, struct.pack(">BHH", WRITE_SINGLE_REGISTER, wire_address, value))


def wire_address_for(register_key: int, zero_mode: bool) -> int:
    """PDU address a client must send to reach a register-map key.

    With the default ``ZERO_MODE=false`` the server adds 1 to the wire address, so
    dict key ``N`` is reached by sending ``N - 1`` (standard 1-based Modbus numbering).
    """
    return register_key if zero_mode else register_key - 1


def to_signed_16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def to_signed_32(value: int) -> int:
    return value - 0x1_0000_0000 if value & 0x8000_0000 else value
