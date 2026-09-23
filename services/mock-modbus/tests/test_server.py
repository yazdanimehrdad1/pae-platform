"""
Test script for the mock Modbus server.

Uses raw TCP sockets with the Modbus protocol to avoid pymodbus version issues.
Run with:  python tests/test_server.py [--host HOST] [--port PORT] [--unit-id ID]
"""

from __future__ import annotations

import argparse
import socket
import struct
import sys


def build_read_registers_request(
    address: int,
    count: int,
    unit_id: int,
    function_code: int,
    transaction_id: int = 1,
) -> bytes:
    """Build a raw Modbus TCP request frame."""
    pdu = struct.pack(">BHH", function_code, address, count)
    length = len(pdu) + 1  # +1 for unit_id byte
    mbap = struct.pack(">HHHB", transaction_id, 0, length, unit_id)
    return mbap + pdu


def parse_read_registers_response(data: bytes) -> list[int]:
    """Parse a Modbus TCP response and return register values."""
    if len(data) < 9:
        raise ValueError(f"Response too short: {len(data)} bytes")

    function_code = data[7]

    if function_code & 0x80:
        exception_code = data[8]
        exceptions = {
            1: "ILLEGAL FUNCTION",
            2: "ILLEGAL DATA ADDRESS",
            3: "ILLEGAL DATA VALUE",
            4: "SERVER DEVICE FAILURE",
        }
        name = exceptions.get(exception_code, f"UNKNOWN ({exception_code})")
        raise ValueError(f"Modbus exception: {name}")

    byte_count = data[8]
    register_data = data[9 : 9 + byte_count]
    registers = []
    for i in range(0, byte_count, 2):
        registers.append(struct.unpack(">H", register_data[i : i + 2])[0])
    return registers


def read_holding_registers(
    sock: socket.socket, address: int, count: int, unit_id: int, tx_id: int
) -> list[int]:
    request = build_read_registers_request(address, count, unit_id, 0x03, tx_id)
    sock.sendall(request)
    response = sock.recv(1024)
    return parse_read_registers_response(response)


def read_input_registers(
    sock: socket.socket, address: int, count: int, unit_id: int, tx_id: int
) -> list[int]:
    request = build_read_registers_request(address, count, unit_id, 0x04, tx_id)
    sock.sendall(request)
    response = sock.recv(1024)
    return parse_read_registers_response(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the mock Modbus server")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=502, help="Server port (default: 502)")
    parser.add_argument("--unit-id", type=int, default=1, help="Modbus unit ID (default: 1)")
    args = parser.parse_args()

    print(f"Connecting to {args.host}:{args.port} (unit {args.unit_id})...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((args.host, args.port))
    except (ConnectionRefusedError, OSError) as e:
        print(f"FAIL - Could not connect: {e}")
        sys.exit(1)

    print("Connected!\n")
    tx_id = 0
    passed = 0
    failed = 0

    # --- Holding register tests ---
    holding_tests = [
        (0, 2, "holding_register 0-1 (voltage/percentage)"),
        (10, 1, "holding_register 10 (power 1000-2000)"),
        (200, 1, "holding_register 200 (full range)"),
        (1000, 1, "holding_register 1000 (voltage 200-240)"),
    ]

    print("=== Holding Registers (FC 0x03) ===")
    for address, count, label in holding_tests:
        tx_id += 1
        try:
            values = read_holding_registers(sock, address, count, args.unit_id, tx_id)
            print(f"  PASS  {label}: {values}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {label}: {e}")
            failed += 1

    # --- Input register tests ---
    input_tests = [
        (0, 1, "input_register 0 (range 300-500)"),
        (50, 1, "input_register 50 (range 100-200)"),
        (2000, 1, "input_register 2000 (range 0-1000)"),
    ]

    print("\n=== Input Registers (FC 0x04) ===")
    for address, count, label in input_tests:
        tx_id += 1
        try:
            values = read_input_registers(sock, address, count, args.unit_id, tx_id)
            print(f"  PASS  {label}: {values}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {label}: {e}")
            failed += 1

    # --- Edge case: read unmapped register (should return default 0) ---
    tx_id += 1
    print("\n=== Edge Cases ===")
    try:
        values = read_holding_registers(sock, 9999, 1, args.unit_id, tx_id)
        print(f"  PASS  Unmapped holding_register 9999 (expect default): {values}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  Unmapped holding_register 9999: {e}")
        failed += 1

    sock.close()

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    else:
        print("All tests passed!")


if __name__ == "__main__":
    main()
